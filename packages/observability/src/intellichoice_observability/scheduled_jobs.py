"""One structured record per nightly job, so "it ran" and "it did anything" are separable.

**The gap this closes (D-377).** The four enabled schedules reported entirely through
`print()`. That output does reach CloudWatch — the ops task runs them in ECS — as unstructured
text, which is the difference between a log and a record. `pipeline.tf` makes exactly this
argument and fixed it for the question-generation pipeline and the deploy-time loader only;
the daily jobs were never included. A three-day query for structured events over the ops-task
log group returned `curriculum_load_complete` and nothing else.

**Read live from staging on 2026-08-16**, the consolidation run that day:

    Consolidation run complete: 7 of 7 student(s), 0 added, 4 reconfirmed,
    ... 14.11 cents spent; 14 model call(s), 0 failed, 3181 event(s) dropped

Zero facts added, 3,181 events dropped over the call cap, and real money spent. **A job
succeeding at doing nothing**, visible only as prose to whoever thought to open the stream.
"Has the 90-day chat purge actually deleted anything this month, or has it been exiting 0
against a broken cutoff since the last deploy?" could not be answered from metrics at all.

**The `job` field is the dimension, and it must match the Terraform job key**
(`terraform/modules/scheduled-jobs/main.tf`'s `locals.jobs`), because the heartbeat alarm is
per job and a mismatch produces an alarm that can never clear. `JOB_*` constants below are the
single source for both sides.

The `print()` calls are deliberately kept. They are what a human sees when running a job by
hand, which is how every one of these is first exercised (the AUD-F-34 lesson: a job whose
first scheduled run is also its first run at all can fail, exit 0, and be read as evidence).
"""

import logging
from typing import Any

from intellichoice_observability.logging_config import configure_logging

logger = logging.getLogger(__name__)

# The Terraform job keys, verbatim. Hyphenated because that is what `locals.jobs` uses and
# what the alarm's `job` dimension will match.
JOB_SESSION_CONSOLIDATE = "session-consolidate"
JOB_CHAT_PURGE = "chat-purge"
JOB_RETENTION_PURGE = "retention-purge"
JOB_MEMORY_CONSOLIDATE = "memory-consolidate"
JOB_YOUTUBE_SYNC = "youtube-sync"
# The one key with no `locals.jobs` entry yet: the checkpoint-retention job is deliberately
# unscheduled (WORK-23, parked by D-333; UD-7), and it still reports, because "has this ever run,
# and did it delete anything" is exactly as unanswerable for a hand-run job as for a scheduled one
# - more so, since nothing fires it on a cadence. Spelled hyphenated like the others so that
# scheduling it later is a terraform edit against this verbatim key rather than a rename that
# silently orphans every record already emitted under the old spelling.
JOB_CHECKPOINT_RETENTION = "checkpoint-retention"


def report_job_complete(job: str, **counts: Any) -> None:
    """Emit `<job>_job_complete` with the counts the job already computed.

    Called at the end of a job's `main()`, next to its `print()`. Configures logging first
    because these run as one-shot CLIs with no app lifespan to have done it — without a
    handler the record is formatted and dropped, which is the failure mode that made this
    necessary in the first place.

    **Never raises.** A job that did its work and then failed to report is still a job that
    did its work; turning an observability call into an exit code would be a worse trade than
    the blindness it replaces.
    """
    try:
        configure_logging()
        logger.info(
            f"{job.replace('-', '_')}_job_complete",
            extra={"job": job, **counts},
        )
    except Exception:  # noqa: BLE001 - see the docstring; reporting must not fail the job
        logging.getLogger(__name__).warning("job_completion_report_failed", exc_info=True)
