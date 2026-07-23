"""SPEC §18-C3/plan §2.2, §2.5-UX: pure, no-LLM, no-DB tests for deterministic
suggestion/follow-up selection.
"""

from chat_api.services.suggestions import (
    category_for_answer,
    category_for_document_id,
    followups_for_answer,
    suggestions_for_role,
)
from intellichoice_db.models.chat import ChatSuggestion


def _suggestion(
    id: str, role_audience: str, category: str, prompt_text: str, sort_order: int = 0
) -> ChatSuggestion:
    return ChatSuggestion(
        id=id,
        role_audience=role_audience,
        category=category,
        prompt_text=prompt_text,
        sort_order=sort_order,
        active=True,
    )


def test_category_for_document_id_maps_known_keywords() -> None:
    assert category_for_document_id("public-branch-directory") == "branches"
    assert category_for_document_id("public-academic-calendar") == "calendar"
    assert category_for_document_id("public-volunteer-guide") == "volunteering"
    assert category_for_document_id("public-student-participation-guide") == "student_participation"
    assert category_for_document_id("public-our-team") == "general"


def test_category_for_answer_prefers_intent_over_citations() -> None:
    assert category_for_answer("branch_locator", ["public-our-team"]) == "branches"
    assert category_for_answer("calendar", []) == "calendar"
    assert category_for_answer("document_qa", ["public-branch-directory"]) == "branches"
    assert category_for_answer("document_qa", []) == "general"
    assert category_for_answer(None, []) == "general"


def test_suggestions_for_role_filters_to_public_and_own_role() -> None:
    pool = [
        _suggestion("s1", "public", "general", "public prompt"),
        _suggestion("s2", "tutor", "general", "tutor prompt"),
        _suggestion("s3", "parent", "general", "parent prompt"),
    ]

    result = suggestions_for_role(pool, user_role="tutor")

    assert "public prompt" in result
    assert "tutor prompt" in result
    assert "parent prompt" not in result


def test_suggestions_for_role_respects_limit() -> None:
    pool = [_suggestion(f"s{i}", "public", "general", f"prompt {i}") for i in range(6)]
    result = suggestions_for_role(pool, user_role="public", limit=2)
    assert result == ["prompt 0", "prompt 1"]


def test_followups_for_answer_prefers_same_category_then_general() -> None:
    pool = [
        _suggestion("branches-1", "public", "branches", "branches prompt", sort_order=0),
        _suggestion("general-1", "public", "general", "general prompt", sort_order=1),
        _suggestion("calendar-1", "public", "calendar", "calendar prompt", sort_order=2),
    ]

    result = followups_for_answer(
        pool, user_role="public", category="branches", asked_query="something else"
    )

    assert result[0] == "branches prompt"
    assert "calendar prompt" not in result
    assert "general prompt" in result


def test_followups_for_answer_never_repeats_the_asked_query() -> None:
    pool = [_suggestion("s1", "public", "general", "Which branch is nearest to me?")]
    result = followups_for_answer(
        pool,
        user_role="public",
        category="general",
        asked_query="Which branch is nearest to me?",
    )
    assert result == []


def test_followups_for_answer_respects_role_and_limit() -> None:
    pool = [
        _suggestion("t1", "tutor", "general", "tutor-only prompt"),
        _suggestion("p1", "public", "general", "public prompt 1"),
        _suggestion("p2", "public", "general", "public prompt 2"),
    ]
    result = followups_for_answer(
        pool, user_role="public", category="general", asked_query="", limit=1
    )
    assert result == ["public prompt 1"]
