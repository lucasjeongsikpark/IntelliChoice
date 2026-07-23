"""SPEC §18-C3/plan §2.2, §2.5-UX: deterministic, category-based suggestions - the
welcome card's initial prompt set and each answer's follow-up chips. No LLM is involved
anywhere in this module (CLAUDE.md non-negotiable #7 is moot here - there's no paid-API
call to bound); `chat_suggestions` rows are hand-authored, seeded via
`make chat-suggestions-load` (`chat_api.services.suggestions_seed`).
"""

from intellichoice_db.models.chat import ChatSuggestion

from chat_api.services.role_access import PUBLIC_AUDIENCE

GENERAL_CATEGORY = "general"

# Maps a `document_id` (see `knowledge-content/manifests/*.yaml`'s own naming) to one of
# `chat_suggestions.category`'s buckets - first substring match wins, so list more
# specific keywords first. Falls back to `GENERAL_CATEGORY` for anything unmapped
# (never an error - an unrecognized document just gets generic follow-ups).
_DOCUMENT_CATEGORY_KEYWORDS: list[tuple[str, str]] = [
    ("branch", "branches"),
    ("calendar", "calendar"),
    ("volunteer", "volunteering"),
    ("participation", "student_participation"),
    ("enrollment", "student_participation"),
]


def category_for_document_id(document_id: str) -> str:
    for keyword, category in _DOCUMENT_CATEGORY_KEYWORDS:
        if keyword in document_id:
            return category
    return GENERAL_CATEGORY


def category_for_answer(intent: str | None, citation_document_ids: list[str]) -> str:
    """Picks a follow-up category for a just-produced answer. `branch_locator`/
    `calendar` intents map directly (no citations to inspect - those two never cite RAG
    chunks); `document_qa` derives it from its top citation's document id.
    """
    if intent == "branch_locator":
        return "branches"
    if intent == "calendar":
        return "calendar"
    if citation_document_ids:
        return category_for_document_id(citation_document_ids[0])
    return GENERAL_CATEGORY


def suggestions_for_role(
    suggestions: list[ChatSuggestion], *, user_role: str, limit: int = 4
) -> list[str]:
    """`GET /chat/meta`'s welcome-card prompt set: every active suggestion the caller's
    role can see (public plus their own role), already in `sort_order` (see
    `ChatSuggestionRepository.list_active`), truncated to `limit`.
    """
    accessible = {PUBLIC_AUDIENCE, user_role}
    pool = [s for s in suggestions if s.role_audience in accessible]
    return [s.prompt_text for s in pool[:limit]]


def followups_for_answer(
    suggestions: list[ChatSuggestion],
    *,
    user_role: str,
    category: str,
    asked_query: str,
    limit: int = 3,
) -> list[str]:
    """Per-answer follow-up chips: same-category suggestions first, then the general
    pool as filler so there's always something to show. Never repeats the question the
    caller just asked (exact, case-insensitive match).
    """
    accessible = {PUBLIC_AUDIENCE, user_role}
    asked = asked_query.strip().lower()

    def _pool(cat: str) -> list[ChatSuggestion]:
        return [
            s
            for s in suggestions
            if s.role_audience in accessible
            and s.category == cat
            and s.prompt_text.strip().lower() != asked
        ]

    ordered = _pool(category)
    if category != GENERAL_CATEGORY:
        ordered += [s for s in _pool(GENERAL_CATEGORY) if s not in ordered]

    seen: set[str] = set()
    result: list[str] = []
    for suggestion in ordered:
        if suggestion.prompt_text in seen:
            continue
        seen.add(suggestion.prompt_text)
        result.append(suggestion.prompt_text)
        if len(result) >= limit:
            break
    return result
