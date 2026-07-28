"""Roll a checkpoint back to what the database can actually support (AUD-X-07).

Two stores commit at two different times, in a fixed order, with nothing coordinating
them: LangGraph's saver commits the **checkpoint** at the end of each superstep on its own
psycopg pool, and the domain rows commit at FastAPI **dependency teardown**, after the
route returns. Anything that fails in between keeps the checkpoint and discards the rows -
FastAPI throws the exception in at `get_db_session`'s `yield`, so `session.commit()` never
runs. A task stop enters that window with no bug required, and ECS drains tasks on every
deploy.

The seam only bites where the checkpoint carries a **domain row id**: an ordinary answer
lives entirely in domain tables, so both stores discard together and stay consistent. Where
it does bite, the old failure mode was a bare `assert` on the promised row, which is a 500
on every subsequent request - the session became a dead end that still rendered a question,
with no route forward through the API at all.

This module is fix shape (2) from the finding: make the divergence *recoverable* instead of
fatal. It does not fix the ordering - that needs the saver to share the request's
connection, which is a much larger change and stays open. What it guarantees is that a
session which entered the window heals on the next request instead of 500ing forever.

Deliberately narrow. It repairs only divergences it can prove, by checking a checkpointed
id against the row it names, and it always rolls *backwards* to a state the database
already supports - it never invents domain rows to match the checkpoint.
"""

import logging
from dataclasses import dataclass

from intellichoice_db.repositories.assessment import AssessmentRepository
from intellichoice_db.repositories.study import StudyRepository

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Repair:
    """One applied repair: the checkpoint values to write, and why."""

    updates: dict
    reason: str


async def find_repair(
    *,
    state: dict,
    assessment_repo: AssessmentRepository,
    study_repo: StudyRepository,
) -> Repair | None:
    """Return the checkpoint correction this session needs, or `None` if consistent.

    Pure detection - the caller applies it, so the check can be run from a read path
    without that read acquiring the power to mutate state by accident.
    """
    phase = state.get("phase")

    # (a) mid-finalize. `_complete_pre_exam` advanced the checkpoint to `study` with a
    # `study_session_id`, then the request died before the domain transaction committed,
    # so the study session it names was never inserted. Reproduced in S38: `POST /resume`
    # returns 200 and serves a study question, answering it 500s, every retry 500s, and
    # `GET /exam/overview` refuses with "not in an exam phase" - no way back.
    study_session_id = state.get("study_session_id")
    if phase == "study" and study_session_id is not None:
        if await study_repo.get_study_session(study_session_id) is None:
            pre_id = state.get("pre_assessment_session_id")
            pre_row = (
                await assessment_repo.get_session(pre_id) if pre_id is not None else None
            )
            # The exam row is the authority on whether the finalize actually landed
            # (`flow.finalize_exam` reads `finalized_at` for exactly this reason). It
            # committed on the same transaction the study session did, so if the study
            # session is missing this should be un-finalized too - but check rather than
            # assume, because rolling a genuinely finalized exam back would re-run
            # scoring.
            if pre_row is not None and pre_row.finalized_at is None:
                return Repair(
                    updates={"study_session_id": None, "phase": "pre_exam"},
                    reason=(
                        f"checkpoint referenced study_session {study_session_id}, which does "
                        "not exist; the pre-exam is not finalized, so the finalize turn was "
                        "lost between the two commits - rolling back to pre_exam"
                    ),
                )
            logger.error(
                "session references a missing study_session %s but its pre-exam is "
                "finalized - not repairable by rollback, needs operator attention",
                study_session_id,
            )
            return None

    # (b) mid-interrupt is NOT handled here, and the omission is deliberate rather than an
    # oversight. `submit_answer` writes a `study_attempts` row and pauses on `interrupt()`
    # for the hint/solution/video choice; if the row is discarded, `/respond` 500s on
    # `update_intervention_choice`'s assert and the interrupt never clears.
    #
    # Detecting it is easy - the checkpoint's `last_study_attempt_id` names a row that is
    # not in `study_repo.get_attempts`. Recovering is not: the session is paused on a
    # LangGraph task, `_get_state_values` refuses any request while one is pending, and
    # clearing it means completing the paused node rather than editing channel values. A
    # detection branch that cannot act on what it finds would be code no test can watch
    # mattering, which this session's other two fixes were each held to.
    #
    # So seam (b) stays open and AUD-X-07 stays open with it. See PROGRESS.md.

    return None
