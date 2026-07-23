"""SPEC §18-C3/plan §13: golden Q&A coverage eval - a regression gate for retrieval
config changes, derived from real ingested content plus synthetic role-gated fixtures
(see `tests/fixtures/qa_coverage_eval.yaml`'s own docstring for the full design and the
mock-reranker query-wording caveat).

Split threshold (user-confirmed at S19 start, given only 3 of the 22 seeded documents
are `effective_from` today - PROGRESS.md's date-gate carryover): refusal-correctness and
no-hallucination need a high bar across the whole 40-question set (they don't depend on
real content being effective); citation-grounding is measured only over the subset
targeting the 3 currently-effective real documents, at a lower, separately-tracked
threshold - self-resolving once more real content passes 2026-08-01.
"""

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import yaml
from chat_api.graph.build import AskInput, build_graph
from chat_api.graph.nodes import TurnContext
from chat_api.services.rate_limit import InMemoryRateLimiter
from intellichoice_adapters.bedrock.gateway import ResilientBedrockGateway
from intellichoice_adapters.bedrock.mock_provider import MockBedrockProvider
from intellichoice_db.models.rag import RagChunk, RagDocument
from intellichoice_db.repositories.interrupts import InterruptApprovalRepository
from intellichoice_db.repositories.mcp import McpToolCallRepository
from intellichoice_db.repositories.org import OrgEventRepository
from intellichoice_db.repositories.rag import RagRepository
from intellichoice_shared.bedrock import BedrockTask
from intellichoice_shared.mcp import McpToolRegistry
from intellichoice_shared.profiles import (
    AttendanceStatus,
    BranchInfo,
    ParentProfile,
    StudentProfile,
)
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver

from .conftest import postgres_skip_reason, rollback_session

pytestmark = pytest.mark.skipif(
    (_reason := postgres_skip_reason()) is not None, reason=_reason or ""
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "qa_coverage_eval.yaml"

# Agreed thresholds (plan §13 / S19 session-start decision) - see module docstring.
# The mock's deterministic keyword/hash-based retrieval currently hits 9/9 (100%) on the
# `grounded` subset with this fixture set's wording - 0.85 leaves room for one case to
# regress before failing the suite, rather than requiring a perfect score forever.
REFUSAL_CORRECTNESS_THRESHOLD = 0.95
NO_HALLUCINATION_THRESHOLD = 0.95
CITATION_GROUNDING_THRESHOLD = 0.85


class _FakeProfileAdapter:
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


def _gateway() -> ResilientBedrockGateway:
    mock = MockBedrockProvider()
    return ResilientBedrockGateway(
        provider=mock,
        embedding_provider=mock,
        model_registry={
            BedrockTask.SCOPE_AND_INTENT: "test-model",
            BedrockTask.RERANK: "test-model",
            BedrockTask.RAG_ANSWER: "test-model",
            BedrockTask.CALENDAR_EXTRACTION: "test-model",
            BedrockTask.EMBEDDING: "amazon.titan-embed-text-v2:0",
        },
        session_budget_cents=50.0,
    )


def _config(thread_id: str) -> RunnableConfig:
    return {"configurable": {"thread_id": thread_id}}


async def _seed_chunk(session, *, audience: str, chunk_text: str) -> None:
    repo = RagRepository(session)
    document = await repo.create_document(
        RagDocument(
            title=f"Eval {audience} document",
            source_path=f"eval/{audience}/doc.md",
            audience=audience,
            academic_year="2026-2027",
            effective_from=datetime.now(UTC),
            status="approved",
            source_sha256="b" * 64,
        )
    )
    embedding_result = await _gateway().create_embedding(
        texts=[chunk_text], session_spend_cents=0.0
    )
    chunk = await repo.add_chunk(
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
            embedding=embedding_result.vectors[0],
        )
    )
    await repo.refresh_search_vectors(document.document_id)
    del chunk


async def _ask(session, *, query: str, thread_id: str) -> dict:
    graph = build_graph(InMemorySaver())
    ctx = TurnContext(
        claims=None,
        profile_adapter=_FakeProfileAdapter(),
        rag_repo=RagRepository(session),
        bedrock_gateway=_gateway(),
        interrupt_repo=InterruptApprovalRepository(session),
        mcp_registry=McpToolRegistry(),
        mcp_call_repo=McpToolCallRepository(session),
        org_event_repo=OrgEventRepository(session),
        rate_limiter=InMemoryRateLimiter(max_per_window=1000, window_s=3600.0),
        admin_escalation_email="admin@example.test",
        query=query,
    )
    return await graph.ainvoke(
        AskInput(session_id=thread_id, query=query), config=_config(thread_id), context=ctx
    )


def _load_cases() -> list[dict[str, Any]]:
    return yaml.safe_load(FIXTURE_PATH.read_text())["cases"]


def test_qa_coverage_eval() -> None:
    cases = _load_cases()

    async def run() -> list[tuple[dict[str, Any], dict]]:
        results = []
        async with rollback_session() as session:
            for case in cases:
                if "seed" in case:
                    await _seed_chunk(session, **case["seed"])
                if "extra_seed" in case:
                    await _seed_chunk(session, **case["extra_seed"])
                result = await _ask(session, query=case["query"], thread_id=f"eval-{case['id']}")
                results.append((case, result))
        return results

    results = asyncio.run(run())

    # --- refusal correctness: role_gated cases get the right role-guidance hint ---
    role_gated = [(c, r) for c, r in results if c["category"] == "role_gated"]
    correct_role_gated = [
        c["id"]
        for c, r in role_gated
        if r.get("access_hint") is not None
        and r["access_hint"].get("required_role") == c["expected_required_role"]
        and not r.get("citations")
    ]
    role_gated_rate = len(correct_role_gated) / len(role_gated) if role_gated else 1.0

    # --- no-hallucination: out_of_scope/no_source never fabricate a citation ---
    refusal_cases = [(c, r) for c, r in results if c["category"] in ("out_of_scope", "no_source")]
    correct_refusal = [c["id"] for c, r in refusal_cases if not r.get("citations")]
    refusal_rate = len(correct_refusal) / len(refusal_cases) if refusal_cases else 1.0

    # --- citation grounding: only over `grounded` cases (real, effective-today docs) ---
    grounded_cases = [(c, r) for c, r in results if c["category"] == "grounded"]
    correct_grounded = [
        c["id"]
        for c, r in grounded_cases
        if any(
            citation.get("source_reference") == c["expected_document_id"]
            for citation in (r.get("citations") or [])
        )
    ]
    grounded_rate = len(correct_grounded) / len(grounded_cases) if grounded_cases else 1.0

    assert role_gated_rate >= REFUSAL_CORRECTNESS_THRESHOLD, (
        f"role-gated correctness {role_gated_rate:.2f} below "
        f"{REFUSAL_CORRECTNESS_THRESHOLD} - passed: {correct_role_gated}"
    )
    assert refusal_rate >= NO_HALLUCINATION_THRESHOLD, (
        f"no-hallucination rate {refusal_rate:.2f} below {NO_HALLUCINATION_THRESHOLD} - "
        f"passed: {correct_refusal}"
    )
    assert grounded_rate >= CITATION_GROUNDING_THRESHOLD, (
        f"citation-grounding rate {grounded_rate:.2f} below "
        f"{CITATION_GROUNDING_THRESHOLD} - passed: {correct_grounded}"
    )
