"""Shared driver for the Q&A coverage eval: fixture -> real chat graph -> `CaseOutcome`s.

Both runners import this - the mock-backed CI gate (`test_qa_coverage_eval.py`) and the
opt-in paid run against real Bedrock (`test_qa_coverage_eval_real_bedrock.py`). The only
difference between them is the gateway they pass in, which is the whole point: any other
difference would make the two runs incomparable, and comparing them is how the mock's own
retrieval limitations become visible instead of being mistaken for retrieval quality.

Scoring lives in `intellichoice_evals.qa_coverage` (pure, no app imports); this module is
only the plumbing that gets a fixture case through the graph.
"""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from chat_api.config import get_settings
from chat_api.graph.build import AskInput, build_graph
from chat_api.graph.nodes import TurnContext
from intellichoice_db.models.rag import RagChunk, RagDocument
from intellichoice_db.repositories.interrupts import InterruptApprovalRepository
from intellichoice_db.repositories.mcp import McpToolCallRepository
from intellichoice_db.repositories.org import OrgEventRepository
from intellichoice_db.repositories.rag import RagRepository
from intellichoice_evals.qa_coverage import CaseOutcome
from intellichoice_shared.bedrock import BedrockGateway
from intellichoice_shared.mcp import McpToolRegistry
from intellichoice_shared.profiles import (
    AttendanceStatus,
    BranchInfo,
    ParentProfile,
    StudentProfile,
)
from intellichoice_shared.rate_limit import InMemoryRateLimiter
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from sqlalchemy import or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "qa_coverage_eval.yaml"


async def effective_public_document_ids(session: AsyncSession) -> frozenset[str]:
    """Documents a caller with no role could read right now: public audience, approved,
    inside their effective window. Mirrors `ChunkFilters`' effectiveness predicate
    (status/effective_from/effective_to, inclusive bounds) at document level.

    Serves two AUD-C-17 duties in `run_all`: the adversarial scorer treats these as
    contained (citing one is answering from content the caller could have read anyway),
    and an *empty* set fails the whole eval rather than letting every containment case
    pass over nothing - the same rule `scan_xray_pii.py` applies to zero traces scanned.
    """
    now = datetime.now(UTC)
    rows = await session.execute(
        select(RagDocument.document_id)
        .where(RagDocument.audience == "public")
        .where(RagDocument.status == "approved")
        .where(RagDocument.effective_from <= now)
        .where(or_(RagDocument.effective_to.is_(None), RagDocument.effective_to >= now))
    )
    return frozenset(rows.scalars())


class FakeProfileAdapter:
    """Every case runs anonymously (SPEC §5.19.1's widest, least-privileged audience), so
    no profile is ever resolved - anything but `get_student_profile` is unreachable and
    says so loudly rather than returning a plausible-looking default.
    """

    async def get_student_profile(self, student_external_id: str) -> StudentProfile | None:
        return None

    async def get_parent_profile(self, parent_external_id: str) -> ParentProfile | None:
        raise NotImplementedError

    async def get_parent_children(self, parent_external_id: str) -> list[str]:
        raise NotImplementedError

    async def get_current_week_attendance(self, student_external_id: str) -> AttendanceStatus:
        raise NotImplementedError

    async def get_branch(self, branch_external_id: str) -> BranchInfo | None:
        raise NotImplementedError

    async def get_branch_manager_email(self, branch_external_id: str) -> str | None:
        raise NotImplementedError

    async def list_branches(self) -> list[BranchInfo]:
        raise NotImplementedError


def load_cases(*, include_mock_only: bool = True) -> list[dict[str, Any]]:
    """AUD-C-21/D-166: `include_mock_only=False` drops cases whose queries only mean something
    to `MockBedrockProvider` - today the five nonsense-marker `role_gated` cases, which a real
    scope guard refuses as out_of_scope before retrieval, so under a real model they measure
    the marker design rather than the feature. The fixture explains each one.
    """
    cases: list[dict[str, Any]] = yaml.safe_load(FIXTURE_PATH.read_text())["cases"]
    if include_mock_only:
        return cases
    return [case for case in cases if not case.get("mock_only")]


async def seed_chunk(
    session: AsyncSession, gateway: BedrockGateway, *, audience: str, chunk_text: str
) -> None:
    repo = RagRepository(session)
    document = await repo.create_document(
        RagDocument(
            title=f"Eval {audience} document",
            source_path=f"eval/{audience}/{abs(hash(chunk_text)) % 10**8}.md",
            audience=audience,
            academic_year="2026-2027",
            effective_from=datetime.now(UTC),
            status="approved",
            source_sha256="b" * 64,
        )
    )
    embedding = await gateway.create_embedding(texts=[chunk_text], session_spend_cents=0.0)
    await repo.add_chunk(
        RagChunk(
            document_id=document.document_id,
            chunk_text=chunk_text,
            document_title=document.title,
            audience=audience,
            access_level=audience,
            academic_year="2026-2027",
            effective_from=document.effective_from,
            status="approved",
            source_sha256="b" * 64,
            embedding=embedding.vectors[0],
        )
    )
    await repo.refresh_search_vectors(document.document_id)


async def reembed_corpus(session: AsyncSession, gateway: BedrockGateway) -> int:
    """Re-embed every approved chunk with `gateway`'s embedding provider, in place.

    A stored embedding is only comparable to a query embedding produced by the *same*
    model: the local corpus was ingested with `MockBedrockProvider`'s hash-based vectors,
    so running the eval against real Bedrock without this step would compare a real Titan
    query vector against fake document vectors and measure nothing but noise in the
    semantic half of the hybrid search. Only the real-Bedrock runner calls this, and only
    inside its rolled-back transaction, so the dev database keeps its mock vectors.

    Nothing in the schema records which model produced a vector, which is why this has to
    be a deliberate step rather than something the pipeline could detect - see
    docs/AUDIT_FINDINGS.md (AUD-C).
    """
    rows = (
        await session.execute(
            text("SELECT chunk_id, chunk_text FROM rag_chunks WHERE status = 'approved'")
        )
    ).all()
    for chunk_id, chunk_text in rows:
        embedding = await gateway.create_embedding(texts=[chunk_text], session_spend_cents=0.0)
        await session.execute(
            text("UPDATE rag_chunks SET embedding = :e WHERE chunk_id = :c"),
            {"e": str(embedding.vectors[0]), "c": chunk_id},
        )
    await session.flush()
    return len(rows)


# AUD-C-12/D-172. The mock run must NOT apply the shipped retrieval floor, and this is the
# one place where the two runs deliberately differ in configuration rather than only in
# provider.
#
# `MIN_RERANK_RELEVANCE_SCORE` (0.35) was calibrated against the real reranker, which scores
# "how relevant is this passage" on the prompt's own 0-1 scale. `MockBedrockProvider`'s
# reranker returns *the fraction of query words present in the chunk* - a lexical coverage
# ratio that shares the [0, 1] range and means something else entirely, so a chunk that fully
# answers a twelve-word question can score 0.25. Measured over this fixture: any floor at or
# above 0.25 drops `grounded-team-3` and takes the gated `grounded` category from 88.9% to
# 77.8%, while the real-model sweep says every floor in [0.30, 0.60) keeps all 20 answerable
# cases. Nothing is wrong with either number; they are measurements of different quantities.
#
# So the mock run keeps its pre-D-172 behaviour exactly (floor 0.0), which is what makes its
# history and its comparison against the real run still readable - the same reason this
# module's docstring gives for not gating retrieval-quality categories on the mock at all. The
# shipped floor is exercised by `packages/knowledge/tests/test_retrieval.py` (explicit scores,
# each watched failing at 0.0) and by the real-Bedrock run.
MOCK_MIN_RELEVANCE_SCORE = 0.0


async def ask(
    session: AsyncSession,
    gateway: BedrockGateway,
    *,
    query: str,
    thread_id: str,
    min_relevance_score: float | None = None,
) -> dict:
    """AUD-C-21/D-166: `access_probe_max_distance` is read from `Settings`, the way the real
    route does (`routers/sessions.py`), not left to `TurnContext`'s own default.

    This was a hole in the instrument, found while trying to make the new wrong-role-hint
    assertion fail on purpose: with the default in play, `CHAT_ACCESS_PROBE_MAX_DISTANCE=0.95`
    changed nothing and the run passed, which looked like the assertion being inert. The two
    values agree today (both come from `access_probe_policy`), so no past measurement was
    wrong - but an eval that cannot see a tuned config cannot be used to tune one.
    """
    graph = build_graph(InMemorySaver())
    ctx = TurnContext(
        claims=None,
        profile_adapter=FakeProfileAdapter(),
        rag_repo=RagRepository(session),
        bedrock_gateway=gateway,
        interrupt_repo=InterruptApprovalRepository(session),
        mcp_registry=McpToolRegistry(),
        mcp_call_repo=McpToolCallRepository(session),
        org_event_repo=OrgEventRepository(session),
        rate_limiter=InMemoryRateLimiter(max_per_window=1000, window_s=3600.0),
        admin_escalation_email="admin@example.test",
        access_probe_max_distance=get_settings().access_probe_max_distance,
        # AUD-C-12/D-172, and the same rule as the line above: the eval must see the tuned
        # value, not `TurnContext`'s default. It matters more here than for the probe, because
        # the two runs need *different* values - see this module's own note below on why a
        # floor calibrated against the real reranker cannot be applied to the mock's scores.
        min_relevance_score=(
            get_settings().retrieval_min_relevance_score
            if min_relevance_score is None
            else min_relevance_score
        ),
        query=query,
    )
    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
    return await graph.ainvoke(
        AskInput(session_id=thread_id, query=query), config=config, context=ctx
    )


def to_outcome(
    case: dict[str, Any], result: dict, public_document_ids: frozenset[str]
) -> CaseOutcome:
    access_hint = result.get("access_hint") or {}
    return CaseOutcome(
        case_id=case["id"],
        category=case["category"],
        answer=result.get("answer") or "",
        citation_document_ids=tuple(
            c.get("source_reference", "") for c in (result.get("citations") or [])
        ),
        access_hint_role=access_hint.get("required_role"),
        escalation_recommended=bool(result.get("escalation_recommended")),
        expected_document_id=case.get("expected_document_id"),
        expected_required_role=case.get("expected_required_role"),
        forbidden_substrings=tuple(case.get("forbidden") or ()),
        allowed_citation_document_ids=tuple(case.get("allowed_citations") or ()),
        public_document_ids=public_document_ids,
    )


async def run_all(
    session: AsyncSession,
    gateway: BedrockGateway,
    *,
    min_relevance_score: float | None = None,
) -> list[CaseOutcome]:
    """Every case on its own thread id, seeded first where the case asks for it.

    Seeds accumulate within the run (the caller's transaction is rolled back afterwards),
    which is deliberate: a later case's retrieval seeing an earlier case's seeded chunk is
    a *harder* test of filtering and refusal, not a contaminated one.

    Refuses to run over an empty effective public corpus (AUD-C-17's recurrence guard,
    the rule `scan_xray_pii.py` applies to zero traces scanned): a containment case
    passes by having nothing to contain, so a run against a fresh database, an
    un-ingested corpus, or all-future `effective_from` dates would go green and mean
    nothing. Honest limit: this catches the *empty* corpus, not the *sparse* one -
    AUD-C-17 itself happened over 3 effective documents that these queries simply never
    retrieved from, which is why the containment verdict is additionally
    corpus-independent by construction (see `_adversarial_passed`). Checked *before* the
    per-case seeds below, which would otherwise mask the emptiness.
    """
    public_document_ids = await effective_public_document_ids(session)
    if not public_document_ids:
        raise AssertionError(
            "qa coverage eval refused to run: no public document is approved and "
            "effective right now, so every containment/refusal case would pass over an "
            "empty corpus and mean nothing (AUD-C-17). Ingest the public corpus (or fix "
            "its effective_from dates) before trusting this eval."
        )
    outcomes = []
    for case in load_cases():
        for key in ("seed", "extra_seed"):
            if key in case:
                await seed_chunk(session, gateway, **case[key])
        result = await ask(
            session,
            gateway,
            query=case["query"],
            thread_id=f"eval-{case['id']}",
            min_relevance_score=min_relevance_score,
        )
        outcomes.append(to_outcome(case, result, public_document_ids))
    return outcomes
