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
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "qa_coverage_eval.yaml"


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


def load_cases() -> list[dict[str, Any]]:
    return yaml.safe_load(FIXTURE_PATH.read_text())["cases"]


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


async def ask(
    session: AsyncSession, gateway: BedrockGateway, *, query: str, thread_id: str
) -> dict:
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
        query=query,
    )
    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
    return await graph.ainvoke(
        AskInput(session_id=thread_id, query=query), config=config, context=ctx
    )


def to_outcome(case: dict[str, Any], result: dict) -> CaseOutcome:
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
    )


async def run_all(session: AsyncSession, gateway: BedrockGateway) -> list[CaseOutcome]:
    """Every case on its own thread id, seeded first where the case asks for it.

    Seeds accumulate within the run (the caller's transaction is rolled back afterwards),
    which is deliberate: a later case's retrieval seeing an earlier case's seeded chunk is
    a *harder* test of filtering and refusal, not a contaminated one.
    """
    outcomes = []
    for case in load_cases():
        for key in ("seed", "extra_seed"):
            if key in case:
                await seed_chunk(session, gateway, **case[key])
        result = await ask(session, gateway, query=case["query"], thread_id=f"eval-{case['id']}")
        outcomes.append(to_outcome(case, result))
    return outcomes
