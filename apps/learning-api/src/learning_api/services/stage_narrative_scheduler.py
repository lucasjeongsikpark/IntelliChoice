"""Study-transition narratives, off the answer's critical path (D-217).

**What was measured.** A correct study-phase answer took **~3.9 s** on staging. The single
largest contributor was the `study_step` stage-narrative Bedrock call (~1.5 s on Haiku
4.5), generated *inside* the answer turn and awaited before the HTTP response returned.
It fires on essentially every first-try-correct study answer (a skill-line transition),
and its per-(session, stage, skill) idempotency key changes every transition, so it never
warm-hits during forward progress. The student waited ~1.5 s per question for a between-
questions overlay the frontend often drops anyway (`interactedPhase` gate, App.tsx).

**The fix, mirroring the consolidation scheduler (D-208).** The answer response no longer
waits: `submit_answer`/`intervention_choice` leave an ids-only marker
(`LearningState.pending_study_narrative`) and return immediately with the next question.
The route hands the marker here; a detached task generates the narrative against its own
session and gateway, then reads the (by-now-committed) checkpoint and publishes a full
snapshot over the SSE bus, so the narrative arrives a beat later exactly like any other
`session_update`.

**Inline vs background.** Selected by provider, in `main.py`: under the mock provider
(dev, and all ~1040 tests) narratives stay **inline** in the graph node - the mock returns
in microseconds, so there is nothing to move off the path and the tests still see
`stage_narrative` on the turn that produced it. This background scheduler is used only when
a real Bedrock call would otherwise block the student.

**Best-effort, stated rather than discovered later** (same posture as D-208): a task still
running when the process is replaced is lost - there is no queue and no retry. Losing one
costs a single between-questions message; it corrupts nothing, because the answer,
mastery, and next question were all committed by the synchronous turn, and the durable
`stage_transitions` row is written before the publish.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from intellichoice_db.repositories.curriculum import CurriculumRepository
from intellichoice_db.repositories.stage_transition import StageTransitionRepository
from intellichoice_db.repositories.study import StudyRepository
from intellichoice_shared.bedrock import BedrockGateway
from intellichoice_shared.profiles import ProfileAdapter
from langchain_core.runnables import RunnableConfig
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from learning_api.services import stage_narrative
from learning_api.services.session_events import SessionEventBus

if TYPE_CHECKING:
    from learning_api.graph.build import LearningGraph

logger = logging.getLogger(__name__)


def _help_is_on_screen(values: dict) -> bool:
    """Whether the student is currently looking at a hint, solution or video (D-358).

    **Two conditions, because the pause covers only one of them.**
    `hint_ladder_awaiting_choice` means the graph is parked on `intervention_choice`, which
    is true while the ladder is open — hints 1 and 2. It is false at every *terminal* rung:
    hint 3 of 3, any solution, any video all close the pause and hand back the next
    question while the help stays on screen. `App.tsx` renders help on
    `ladderOpen || intervention != null` for exactly that reason, and this is the
    server-side reading of the same thing.

    **The second condition is a pairing, not a presence check.** `last_intervention` goes
    stale on purpose — `submit_answer` advances `last_study_attempt_id` without clearing it
    — so "there is an intervention" stays true long after the student has moved on. Asking
    whether it belongs to the *current* attempt is what makes this a question about the
    screen rather than about history, and it is why D-358 added the companion channel
    instead of reading `last_intervention` alone. Getting that wrong in the permissive
    direction erases a student's video; getting it wrong in the other direction silently
    suppresses every narrative after the first hint of the session.
    """
    if values.get("hint_ladder_awaiting_choice"):
        return True
    if values.get("last_intervention") is None:
        return False
    return values.get("last_intervention_attempt_id") == values.get("last_study_attempt_id")


class BackgroundStudyNarrativeScheduler:
    """Generates a deferred study-transition narrative in a detached task and publishes
    the resulting snapshot over the SSE bus. Constructed once in the app lifespan.
    """

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker,
        gateway_factory: Callable[[], BedrockGateway],
        graph_getter: "Callable[[], LearningGraph]",
        events: SessionEventBus,
        profile_adapter: ProfileAdapter,
        snapshot_builder: Callable[
            [AsyncSession, str, dict, str, list[str], str | None], Awaitable[dict]
        ],
    ) -> None:
        self._session_factory = session_factory
        self._gateway_factory = gateway_factory
        self._graph_getter = graph_getter
        self._events = events
        self._profile_adapter = profile_adapter
        self._snapshot_builder = snapshot_builder
        # As in the consolidation scheduler: `create_task` holds only a weak reference, so
        # a task with no other referent can be GC'd mid-flight. Keep the set; discard on
        # done so it does not grow.
        self._tasks: set[asyncio.Task] = set()

    async def schedule(
        self, *, learning_session_id: str, student_external_id: str, marker: dict
    ) -> None:
        """Returns as soon as the task is created - this is the whole point."""
        task = asyncio.create_task(
            self._run(
                learning_session_id=learning_session_id,
                student_external_id=student_external_id,
                marker=marker,
            )
        )
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _run(
        self, *, learning_session_id: str, student_external_id: str, marker: dict
    ) -> None:
        try:
            async with self._session_factory() as session:
                payload, related = await stage_narrative.payload_from_marker(
                    profile_adapter=self._profile_adapter,
                    curriculum_repo=CurriculumRepository(session),
                    study_repo=StudyRepository(session),
                    student_external_id=student_external_id,
                    marker=marker,
                )
                result = await stage_narrative.generate_stage_narrative(
                    gateway=self._gateway_factory(),
                    repo=StageTransitionRepository(session),
                    student_external_id=student_external_id,
                    learning_session_id=learning_session_id,
                    payload=payload,
                    related_skill_id=related,
                    # Own budget line - there is no request total to share, same as D-208.
                    session_spend_cents=0.0,
                )
                await session.commit()

            # Read the checkpoint *after* generating: the ~1.5s call means the answer turn
            # (which returned in ~200ms) has long since committed, so this sees the next
            # question already served rather than the state mid-turn.
            config: RunnableConfig = {"configurable": {"thread_id": learning_session_id}}
            snapshot = await self._graph_getter().aget_state(config)
            if _help_is_on_screen(snapshot.values):
                # D-272, second layer; widened by D-358. The publish below omits
                # `pending_interrupt`, `intervention` and `assistance_question` —
                # deliberately, per this class's docstring, because "a study-transition
                # narrative only fires when the turn advanced". That was a claim about
                # *when narratives fire*, and it stopped being true the moment a stale
                # marker could fire one during a pause: the frame then wiped the hint a
                # student had just asked for off their screen.
                #
                # The stale marker itself is fixed in `nodes._study_narrative_update`. This
                # is the belt: whatever schedules a narrative, it must never be published
                # over help the student is reading. Nothing is lost — the durable
                # `stage_transitions` row is already written, and the narrative was a
                # between-questions message for a moment that is no longer between
                # questions.
                logger.info(
                    "stage_narrative_publish_skipped_help_on_screen learning_session=%s",
                    learning_session_id,
                )
                return
            if snapshot.values:
                # D-272: a second, short-lived session. The snapshot now carries
                # `study_progress`, which is read from the study rows, and the session
                # above is already closed by here - deliberately, since the narrative call
                # sits between them and holding a connection across it would tie up a pool
                # slot for ~1.5s per background narrative.
                #
                # This frame *replaces* the client's whole snapshot, so anything it omits
                # is erased from the screen. Leaving the counters out would have blanked
                # the progress bar a second after every correct answer.
                async with self._session_factory() as snapshot_session:
                    event = await self._snapshot_builder(
                        snapshot_session,
                        learning_session_id,
                        snapshot.values,
                        result.narrative_text,
                        result.evidence_summary,
                        # U3/D-325: taken from the payload that produced this text, so a
                        # deferred `study_step` frame is titled as one.
                        payload.stage,
                    )
                self._events.publish(learning_session_id, event)
        except Exception:
            # Swallowed on purpose (same reasoning as the consolidation scheduler): nothing
            # awaits this, and an exception escaping a detached task only surfaces as "Task
            # exception was never retrieved" at GC time. Logged with a stack trace instead.
            logger.exception("background_study_narrative_failed")
