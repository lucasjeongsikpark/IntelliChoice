"""SPEC §18-C3/plan §2.2, §2.5-UX: `GET /chat/meta`'s welcome text + role-aware
suggestions, and the deterministic welcome-excerpt service it's built on. Calls the
router function directly (not via `TestClient`) so seeded rows stay isolated inside
`rollback_session`, mirroring `apps/chat-api/tests/test_qa_service.py`'s style for
testing a service/route function without a live HTTP round trip.
"""

import asyncio
from datetime import datetime

import pytest
from chat_api.routers.meta import get_chat_meta
from chat_api.services.welcome import (
    FALLBACK_WELCOME_TEXT,
    ORGANIZATION_OVERVIEW_DOCUMENT_ID,
    _first_two_sentences,
    get_welcome_text,
)
from intellichoice_db.models.chat import ChatSuggestion
from intellichoice_db.repositories.chat import ChatSuggestionRepository
from intellichoice_db.repositories.rag import RagRepository
from intellichoice_shared.auth import Audience, Role, TokenClaims
from intellichoice_shared.profiles import (
    AttendanceStatus,
    BranchInfo,
    ParentProfile,
    StudentProfile,
)

from .conftest import postgres_skip_reason, rollback_session

pytestmark = pytest.mark.skipif(
    (_reason := postgres_skip_reason()) is not None, reason=_reason or ""
)


class _FakeProfileAdapter:
    async def get_student_profile(self, student_external_id: str) -> StudentProfile | None:
        raise NotImplementedError

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


def _claims(role: Role) -> TokenClaims:
    return TokenClaims(
        sub="zqxvmeta-1",
        role=role,
        account_status="active",
        consent_status="granted",
        parental_consent_verified=True,
        consent_version="v1",
        issued_at=datetime.fromisoformat("2026-01-01T00:00:00+00:00"),
        expires_at=datetime.fromisoformat("2027-01-01T00:00:00+00:00"),
        audience=Audience.CHAT,
    )


def test_first_two_sentences_strips_heading_and_truncates() -> None:
    text = (
        "### About Us\n\nZqxvmeta is a nonprofit that supports volunteers. It offers "
        "free tutoring. A third sentence should be dropped from the excerpt."
    )
    excerpt = _first_two_sentences(text)
    assert excerpt == (
        "Zqxvmeta is a nonprofit that supports volunteers. It offers free tutoring."
    )
    assert "About Us" not in excerpt
    assert "third sentence" not in excerpt


def test_first_two_sentences_caps_length() -> None:
    long_sentence = "Word " * 100 + "."
    excerpt = _first_two_sentences(long_sentence)
    assert len(excerpt) <= 320


def test_welcome_text_falls_back_for_an_unknown_document() -> None:
    async def run() -> None:
        async with rollback_session() as session:
            repo = RagRepository(session)
            text = await get_welcome_text(repo, document_id="zqxvmeta-no-such-document")
            assert text == FALLBACK_WELCOME_TEXT

    asyncio.run(run())


def test_welcome_text_excerpts_the_real_ingested_about_document() -> None:
    """Integration check against the real `public-organization-overview` document
    (S17) - already `effective_from` today, so this is real content, not a fixture.
    Asserts the excerpt's shape/invariants rather than exact wording, since the real
    page's copy can change on a future `webcontent-sync`.
    """

    async def run() -> None:
        async with rollback_session() as session:
            repo = RagRepository(session)
            text = await get_welcome_text(
                repo, document_id=ORGANIZATION_OVERVIEW_DOCUMENT_ID
            )
            if text == FALLBACK_WELCOME_TEXT:
                pytest.skip(
                    "public-organization-overview isn't ingested in this environment "
                    "(run `make knowledge-load`)"
                )
            assert "About Us" not in text
            assert 0 < len(text) <= 320

    asyncio.run(run())


def test_meta_anonymous_caller_gets_only_public_suggestions() -> None:
    async def run() -> None:
        async with rollback_session() as session:
            suggestion_repo = ChatSuggestionRepository(session)
            await suggestion_repo.upsert(
                ChatSuggestion(
                    id="zqxvmeta-public",
                    role_audience="public",
                    category="general",
                    prompt_text="Zqxvmeta public prompt",
                    sort_order=-100,
                    active=True,
                )
            )
            await suggestion_repo.upsert(
                ChatSuggestion(
                    id="zqxvmeta-tutor",
                    role_audience="tutor",
                    category="general",
                    prompt_text="Zqxvmeta tutor-only prompt",
                    sort_order=1,
                    active=True,
                )
            )
            await suggestion_repo.upsert(
                ChatSuggestion(
                    id="zqxvmeta-inactive",
                    role_audience="public",
                    category="general",
                    prompt_text="Zqxvmeta inactive prompt",
                    sort_order=2,
                    active=False,
                )
            )

            meta = await get_chat_meta(
                claims=None, profile_adapter=_FakeProfileAdapter(), db=session
            )

            assert "Zqxvmeta public prompt" in meta.suggested_prompts
            assert "Zqxvmeta tutor-only prompt" not in meta.suggested_prompts
            assert "Zqxvmeta inactive prompt" not in meta.suggested_prompts
            assert meta.welcome_text

    asyncio.run(run())


def test_meta_tutor_caller_also_gets_tutor_suggestions() -> None:
    async def run() -> None:
        async with rollback_session() as session:
            suggestion_repo = ChatSuggestionRepository(session)
            await suggestion_repo.upsert(
                ChatSuggestion(
                    id="zqxvmeta-public-2",
                    role_audience="public",
                    category="general",
                    prompt_text="Zqxvmeta public prompt",
                    sort_order=-100,
                    active=True,
                )
            )
            await suggestion_repo.upsert(
                ChatSuggestion(
                    id="zqxvmeta-tutor-2",
                    role_audience="tutor",
                    category="general",
                    prompt_text="Zqxvmeta tutor-only prompt",
                    sort_order=-99,
                    active=True,
                )
            )

            meta = await get_chat_meta(
                claims=_claims(Role.TUTOR), profile_adapter=_FakeProfileAdapter(), db=session
            )

            assert "Zqxvmeta public prompt" in meta.suggested_prompts
            assert "Zqxvmeta tutor-only prompt" in meta.suggested_prompts

    asyncio.run(run())
