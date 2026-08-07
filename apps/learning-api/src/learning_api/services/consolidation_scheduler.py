"""Memory consolidation, off the request path (D-208).

**What was measured.** `POST /exam/finalize` took **65–81 s** on staging, of which
**61.5 s** was one `memory_consolidation` Bedrock call. The duration was identical to the
millisecond across attempts - `61502.69ms`, `61503.12ms` - which is the signature of a
ceiling being hit rather than of work being done: `bedrock_call_timeout_s = 20.0` times
`1 + max_retries(2)` is exactly 60 s.

And it never produced anything. Across fourteen days of staging logs the task appears
twice, and both are `bedrock_call_failed / provider_unavailable / TimeoutError`, ending in
`"memory consolidation call failed, no facts changed"`. **Semantic memory has never once
consolidated in the deployed environment**, and the only two times it tried, a student sat
through a minute of it to reach a results screen the call contributes nothing to.

The node's own comment said *"Never blocks the response"*. That was true of a *failure* -
`consolidate_student_session` swallows `BedrockGatewayError` - and false of the latency,
which is the part a student experiences. A comment asserting the good property next to the
missing one is a good way for this to go unnoticed for as long as it did.

**Two separate defects, so two separate fixes.**

1. *It was on the request path.* Consolidation writes semantic-memory facts used to
   personalise **later** sessions. Nothing in the finalize response depends on it - the
   learning gain the results screen renders is computed deterministically before this
   runs. So it is scheduled here and the response returns immediately.

2. *Its timeout did not fit its payload.* Consolidation sends up to
   `_MAX_EVENT_TOKENS_PER_CALL` (20 000) tokens of events plus every existing fact, and
   asks for a large structured response; the shared 20 s ceiling is sized for a tutor
   reply (~3-4 s measured). Now that no one is waiting, this runs against a gateway built
   with a ceiling that fits the work.

**Bound to the session factory, not to a request session** - the same reasoning
`get_cost_ledger` already documents. The request's transaction closes when the response is
sent; a task holding that session would be writing into a closed one.

**Best-effort by design, and that is a real limitation, stated rather than discovered
later.** A task still running when the process is replaced is lost - there is no queue and
no retry, and this codebase has no scheduler to catch the gap (`consolidate_student_window`
exists as a CLI but nothing invokes it on a timer). Losing one cycle's consolidation costs
some personalisation quality in later sessions; it corrupts nothing, because facts are
additive and every consumer already handles their absence. A durable queue is the right
answer if this ever needs to be reliable, and it is deliberately not being built here to
fix a latency defect.
"""

import asyncio
import logging
from collections.abc import Callable
from typing import Protocol

from intellichoice_db.repositories.mastery import MasteryRepository
from intellichoice_db.repositories.memory import MemoryRepository
from intellichoice_db.repositories.tutor_chat import TutorChatMessageRepository
from intellichoice_memory.consolidation import consolidate_student_session
from intellichoice_shared.bedrock import BedrockGateway
from sqlalchemy.ext.asyncio import async_sessionmaker

logger = logging.getLogger(__name__)


class ConsolidationScheduler(Protocol):
    """What `nodes.finalize_exam` needs: somewhere to hand the work that is not `await`.

    A Protocol rather than a concrete type so the graph stays testable without an event
    loop or a second database session - `InlineConsolidationScheduler` below keeps the
    pre-D-208 behaviour for tests that assert on the facts a cycle produced.

    `schedule` is **async even though scheduling is not**, so that the inline
    implementation can genuinely finish before returning. A synchronous signature would
    force the inline variant to fire-and-forget too, which is exactly the property the
    existing tests rely on not being fire-and-forget.
    """

    async def schedule(self, *, student_external_id: str, session_id: str) -> None: ...


class BackgroundConsolidationScheduler:
    """Runs consolidation in a detached task with its own session and gateway."""

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker,
        gateway_factory: Callable[[], BedrockGateway],
    ) -> None:
        self._session_factory = session_factory
        self._gateway_factory = gateway_factory
        # `asyncio.create_task` only holds a weak reference, so a task with no other
        # referent can be garbage-collected mid-flight. Keeping the set is the documented
        # way to stop that, and the discard callback keeps it from growing.
        self._tasks: set[asyncio.Task] = set()

    async def schedule(self, *, student_external_id: str, session_id: str) -> None:
        """Returns as soon as the task is created - this is the whole point."""
        task = asyncio.create_task(
            self._run(student_external_id=student_external_id, session_id=session_id)
        )
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _run(self, *, student_external_id: str, session_id: str) -> None:
        try:
            async with self._session_factory() as session:
                result = await consolidate_student_session(
                    memory_repo=MemoryRepository(session),
                    mastery_repo=MasteryRepository(session),
                    tutor_chat_repo=TutorChatMessageRepository(session),
                    gateway=self._gateway_factory(),
                    student_external_id=student_external_id,
                    session_id=session_id,
                    # Its own budget line: this no longer shares a request's running
                    # total, because there is no longer a request to share one with.
                    session_spend_cents=0.0,
                )
                await session.commit()
            # `calls_attempted`/`calls_failed` are logged deliberately: AUD-F-34's whole
            # point is that `added == 0` looks identical for "nothing to consolidate" and
            # "every call failed", and the second is precisely the state staging was in.
            # Nobody is watching this run, so the log line has to carry the distinction.
            logger.info(
                "background_consolidation_complete",
                extra={
                    "added": result.added,
                    "updated": result.updated,
                    "contested": result.contested,
                    "expired": result.expired,
                    "calls_attempted": result.calls_attempted,
                    "calls_failed": result.calls_failed,
                    "events_dropped": result.events_dropped,
                    "cost_cents": result.cost_cents,
                },
            )
        except Exception:
            # Swallowed on purpose: nothing is waiting on this, and an exception escaping
            # a detached task is only ever reported as "Task exception was never
            # retrieved" at garbage-collection time, which is the least findable place a
            # failure can land. Logged with a stack trace instead.
            logger.exception("background_consolidation_failed")


class InlineConsolidationScheduler:
    """Pre-D-208 behaviour, kept for tests.

    The 1000+ existing tests run against `MockBedrockProvider` (microseconds, no network),
    so awaiting here costs nothing and lets assertions about a cycle's consolidated facts
    keep working without an event-loop dance. Never selected in a deployed environment.
    """

    def __init__(
        self,
        *,
        memory_repo: MemoryRepository,
        mastery_repo: MasteryRepository,
        tutor_chat_repo: TutorChatMessageRepository,
        gateway: BedrockGateway,
    ) -> None:
        self._memory_repo = memory_repo
        self._mastery_repo = mastery_repo
        self._tutor_chat_repo = tutor_chat_repo
        self._gateway = gateway

    async def schedule(self, *, student_external_id: str, session_id: str) -> None:
        """Actually runs it, on this request's session, before returning."""
        await consolidate_student_session(
            memory_repo=self._memory_repo,
            mastery_repo=self._mastery_repo,
            tutor_chat_repo=self._tutor_chat_repo,
            gateway=self._gateway,
            student_external_id=student_external_id,
            session_id=session_id,
            session_spend_cents=0.0,
        )
