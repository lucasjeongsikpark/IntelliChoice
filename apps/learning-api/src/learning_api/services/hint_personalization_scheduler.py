"""Hint personalization, off the click's critical path (D-272).

**What was measured.** Clicking "Get a hint" took ~2.3 s on staging, and essentially all of
it is one `HINT_PERSONALIZATION` Bedrock call. Solutions do not pay this - D-207 serves the
authored `canonical_solution` for 0 ms and 0 cost - but every hint did, on every rung.

**What the wait was for.** A rewrite of a sentence the bank already holds. Every failure path
in `tutor.generate_personalized_hint` already falls back to that canonical rung verbatim, and
those rungs have just been through two independent LLM reviewers and a repair loop
(D-251-271). So the instant text is reviewed content, not a placeholder or a spinner.

**The shape, reusing D-217's.** `_hint_round` serves the canonical rung and writes its
`hint_events` row immediately (canonical text, `was_personalized=False` - the exact row
today's failure paths write, so nothing downstream learns a new state). The route hands an
ids-only marker here; a detached task personalizes, completes the row, and publishes a full
snapshot over the SSE bus.

### Two things this deliberately does not do, stated rather than discovered later

1. **It does not write the checkpoint.** Publishing over SSE only means a student who
   *refreshes* mid-hint gets the canonical rung back, not the personalized one. That is a
   downgrade to reviewed content, not to nothing. Writing `last_intervention` from outside a
   graph turn would need `aupdate_state` against a thread a concurrent request may be
   holding, to save a rewrite of a sentence the student can already read - not a trade worth
   making.
2. **Its cost does not reach `bedrock_spend_cents`.** Same as the narrative scheduler and for
   the same reason (D-073/D-075): this never touches the graph, so there is no turn to fold
   the cents into. The `hint_events` row is the audit trail, and the gateway's own
   `session_budget_cents` still bounds the call.

**Staleness is guarded, not hoped for — and the guard was wrong for a year in a way this
paragraph used to describe approvingly (D-373).** It said the task "drops the result unless
`last_study_attempt_id` still names the attempt the hint was for", which covers a student who
*answered again* and misses the student who *switched help*. `intervention_choice` does not
advance that channel, so clicking "Watch a video" mid-rewrite left the guard satisfied and the
published frame replaced the video with hint text — D-356's symptom, in the publisher that
never received D-358's pairing signal or D-369's re-read.

`_hint_is_still_on_screen` now asks whether the student is looking at *this hint*, and it is
evaluated twice: once before the expensive snapshot build and again immediately before the
synchronous publish, because a choice committing in that gap is invisible to a read that has
already happened.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Literal

from intellichoice_db.repositories.curriculum import CurriculumRepository
from intellichoice_db.repositories.hints import HintEventRepository
from intellichoice_db.repositories.mastery import MasteryRepository
from intellichoice_db.repositories.memory import MemoryRepository
from intellichoice_db.repositories.questions import QuestionRepository
from intellichoice_db.repositories.study import StudyRepository
from intellichoice_observability.metrics import HINT_PERSONALIZATION_OUTCOMES
from intellichoice_shared.bedrock import BedrockGateway
from intellichoice_shared.profiles import ProfileAdapter
from langchain_core.runnables import RunnableConfig
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from learning_api.services import topic_resolver, tutor
from learning_api.services.session_events import SessionEventBus

if TYPE_CHECKING:
    from learning_api.graph.build import LearningGraph

logger = logging.getLogger(__name__)

# **The vocabulary for D-329's other half.** Raised failures are watched - the
# `logger.exception` below feeds a live CloudWatch metric filter and an alarm. Nothing watched
# the runs that end *without* raising, and "every call falls back to canonical" is exactly such
# a run: the original ran-dead-in-production mode, silent by construction.
#
# **What the counter makes detectable:** `learning_support_usage_total{support_type="hint"}`
# moving while `learning_hint_personalization_outcomes_total{outcome="published"}` stays flat at
# zero means hints are being served and none of them are being personalized. Whether that should
# raise an alarm is UD-5's held user question, and this names the number rather than answering
# it.
#
# Two groups. `precondition_missing` ends before the paid call, so nothing was spent and
# nothing was owed; the other four end after it, with a durable `hint_events` row and - except
# for `published` - nothing on the student's screen. `dropped_late` folds the empty-checkpoint
# and no-snapshot returns in with the publish-time guard because all three are that same
# terminal shape, and the log lines already tell them apart when one needs telling apart.
_Outcome = Literal[
    "published",
    "fallback_canonical",
    "dropped_stale",
    "dropped_late",
    "precondition_missing",
    "failed",
]


def _hint_is_still_on_screen(values: dict, *, attempt_id: str, level: int) -> bool:
    """Whether the student is still looking at the exact hint this task personalized.

    **The guard this replaces asked the wrong question, and D-356 is the cost.** It compared
    `last_study_attempt_id` to the marker's attempt — but `intervention_choice` does *not*
    advance that channel (only `submit_answer` does). So a student who clicked "Watch a video"
    or "Show the solution" while this task was inside its ~2.3 s Bedrock call was still on the
    same attempt, the guard passed, and the published frame replaced their video with hint
    text. Every SSE frame replaces the client's whole snapshot, and the pause is already
    closed at a terminal rung, so **nothing republishes and a refresh shows no help at all**.

    Four things have to hold, and each rules out a real case:

    - same attempt — the student has not answered and moved on (the original check);
    - the current help is a *hint* — not the video or solution they switched to;
    - at the *same level* — not hint 2 after this task personalized hint 1;
    - and that help belongs to this attempt (`last_intervention_attempt_id`, D-358) — because
      `last_intervention` is never cleared and goes stale by design.

    **Deliberately strict rather than lenient.** A checkpoint written before D-358 shipped has
    no `last_intervention_attempt_id`, so this returns False and the personalization is
    dropped. That is the right direction: the student keeps the canonical hint, which is a
    complete, reviewed hint, whereas the permissive direction erases help they chose.
    """
    if values.get("last_study_attempt_id") != attempt_id:
        return False
    intervention = values.get("last_intervention")
    if not isinstance(intervention, dict) or intervention.get("type") != "hint":
        return False
    if intervention.get("hint_level") != level:
        return False
    return values.get("last_intervention_attempt_id") == attempt_id


class BackgroundHintPersonalizationScheduler:
    """Personalizes an already-served canonical hint in a detached task and publishes the
    replacement over the SSE bus. Constructed once in the app lifespan.
    """

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker,
        gateway_factory: Callable[[], BedrockGateway],
        graph_getter: "Callable[[], LearningGraph]",
        events: SessionEventBus,
        profile_adapter: ProfileAdapter,
        snapshot_builder: Callable[[AsyncSession, str, dict, dict], Awaitable[dict | None]],
    ) -> None:
        self._session_factory = session_factory
        self._gateway_factory = gateway_factory
        self._graph_getter = graph_getter
        self._events = events
        self._profile_adapter = profile_adapter
        self._snapshot_builder = snapshot_builder
        # `create_task` holds only a weak reference, so a task with no other referent can be
        # GC'd mid-flight. Keep the set; discard on done so it does not grow.
        self._tasks: set[asyncio.Task] = set()

    async def schedule(self, *, learning_session_id: str, marker: dict) -> None:
        """Returns as soon as the task is created - this is the whole point."""
        task = asyncio.create_task(self._run(learning_session_id, marker))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _run(self, learning_session_id: str, marker: dict) -> None:
        """One task run, exactly one outcome.

        Counted here rather than at each of the six terminal points inside `_personalize`, so
        "one outcome per run" is a property of the shape instead of six call sites staying
        correct - the failure being instrumented is precisely a path that ends saying nothing.
        """
        outcome = await self._personalize(learning_session_id, marker)
        HINT_PERSONALIZATION_OUTCOMES.labels(outcome=outcome).inc()

    async def _personalize(self, learning_session_id: str, marker: dict) -> _Outcome:
        try:
            async with self._session_factory() as session:
                study_repo = StudyRepository(session)
                question_repo = QuestionRepository(session)
                hint_repo = HintEventRepository(session)

                attempt = await study_repo.get_attempt(marker["attempt_id"])
                if attempt is None:
                    return "precondition_missing"
                variant = await question_repo.get_variant(attempt.question_variant_id)
                if variant is None:
                    return "precondition_missing"
                template = await question_repo.get_template(variant.question_template_id)
                if template is None or not template.hint_ladder:
                    return "precondition_missing"

                ladder = list(template.hint_ladder)
                level = min(int(marker["level"]), len(ladder))
                canonical_text = ladder[level - 1]
                next_canonical_text = ladder[level] if level < len(ladder) else None

                context = await topic_resolver.resolve_tutor_context(
                    profile_adapter=self._profile_adapter,
                    question_repo=question_repo,
                    curriculum_repo=CurriculumRepository(session),
                    mastery_repo=MasteryRepository(session),
                    student_external_id=attempt.student_external_id,
                    question_variant_id=attempt.question_variant_id,
                    selected_option=attempt.selected_option,
                )
                correct_answer_text = await topic_resolver.resolve_correct_answer_text(
                    question_repo=question_repo,
                    question_variant_id=attempt.question_variant_id,
                )
                prior = await hint_repo.get_events_for_attempt(attempt.attempt_id)
                # This rung's own row is already written (canonical), so it has to come out
                # of "what the student was told before" - otherwise the prompt asks the model
                # to say something different from the very text it is rewriting.
                previous_summaries = [
                    event.personalized_hint_text
                    for event in prior
                    if event.hint_event_id != marker["hint_event_id"]
                ]
                relevant_fact = await _relevant_fact(
                    MemoryRepository(session), attempt.student_external_id, template.skill_id
                )

                hint, _cost, was_personalized = await tutor.generate_personalized_hint(
                    gateway=self._gateway_factory(),
                    context=context,
                    canonical_hint_text=canonical_text,
                    next_canonical_hint_text=next_canonical_text,
                    hint_level=level,
                    attempt_count=attempt.retry_count + 1,
                    misconception_tag=topic_resolver.resolve_misconception_tag(
                        template, variant, attempt.selected_option
                    ),
                    previous_hint_summaries=previous_summaries,
                    correct_answer_text=correct_answer_text,
                    relevant_learning_fact=relevant_fact,
                    # Own budget line - there is no request total to share (D-073/D-075).
                    session_spend_cents=0.0,
                )
                await hint_repo.set_personalized(
                    marker["hint_event_id"],
                    personalized_hint_text=hint.hint_text,
                    was_personalized=was_personalized,
                )
                await session.commit()

            if not was_personalized:
                # Every rejection path returns the canonical text verbatim, which is already
                # on the student's screen. Publishing would repaint the panel with identical
                # content - motion for nothing.
                return "fallback_canonical"

            config: RunnableConfig = {"configurable": {"thread_id": learning_session_id}}
            snapshot = await self._graph_getter().aget_state(config)
            if not snapshot.values:
                return "dropped_late"
            if not _hint_is_still_on_screen(
                snapshot.values, attempt_id=marker["attempt_id"], level=level
            ):
                # The student moved on, or switched to a video or solution, while this ran.
                # Dropping it is the only safe move: the row is already complete, and
                # publishing would replace whatever they are looking at now.
                logger.info(
                    "hint_personalization_dropped_stale learning_session=%s",
                    learning_session_id,
                )
                return "dropped_stale"

            content = {
                "type": "hint",
                **hint.model_dump(),
                "hint_level": level,
                "max_hint_level": len(ladder),
            }
            async with self._session_factory() as snapshot_session:
                event = await self._snapshot_builder(
                    snapshot_session, learning_session_id, snapshot.values, content
                )
            # **Re-read and re-check immediately before publishing** (D-369, ported here).
            #
            # The guard above is evaluated once, and the snapshot build between then and now
            # opens a session and queries the study rows. A student who switches to a video
            # in that gap commits their choice *after* the read, so the values the guard
            # inspected cannot contain it — the same defect, one step later. There are no
            # awaits between this check and the synchronous `publish`, so within the process
            # the window is closed rather than narrowed; a commit from another replica in
            # that gap stays possible in principle and is not claimed otherwise.
            latest = await self._graph_getter().aget_state(config)
            if not _hint_is_still_on_screen(
                latest.values, attempt_id=marker["attempt_id"], level=level
            ):
                logger.info(
                    "hint_personalization_dropped_help_changed_late learning_session=%s",
                    learning_session_id,
                )
                return "dropped_late"
            if event is None:
                # The builder found no snapshot to send. Same terminal shape as the drop
                # above - the rewrite is durable in `hint_events` and the screen never
                # changed - so it counts as the same outcome.
                return "dropped_late"
            self._events.publish(learning_session_id, event)
            return "published"
        except Exception:
            # Swallowed on purpose (same reasoning as the other two schedulers): nothing
            # awaits this, and an exception escaping a detached task only surfaces as "Task
            # exception was never retrieved" at GC time. The student keeps the canonical
            # hint, which is a complete, reviewed hint.
            #
            # Unchanged on purpose, and load-bearing: the deployed metric filter behind the
            # `BackgroundTaskFailures` alarm matches `{ $.event = "background_*_failed" }`
            # over this log group, so the message's shape is what keeps that alarm armed.
            logger.exception("background_hint_personalization_failed")
            return "failed"


async def _relevant_fact(
    memory_repo: MemoryRepository, student_external_id: str, skill_id: str
) -> str | None:
    """The same one-fact lookup `nodes._resolve_relevant_fact` does, against this task's own
    session. Duplicated rather than imported because importing `nodes` here would make the
    service layer depend on the graph layer, which nothing else in `services/` does.
    """
    fact = await memory_repo.top_fact_for_skill(student_external_id, skill_id)
    return fact.fact_text if fact is not None else None
