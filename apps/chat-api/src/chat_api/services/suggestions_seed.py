"""`make chat-suggestions-load`: idempotent upsert of chat-web's welcome/follow-up
prompt catalog. Hand-authored reference data (unlike `packages/webcontent`'s scraped org
content) - there's no fetch step, just this module's own `SEED_SUGGESTIONS` list upserted
by natural-key `id`, safe to re-run.
"""

from intellichoice_db.models.chat import ChatSuggestion
from intellichoice_db.repositories.chat import ChatSuggestionRepository
from sqlalchemy.ext.asyncio import AsyncSession

SEED_SUGGESTIONS: list[ChatSuggestion] = [
    ChatSuggestion(
        id="public-general-about",
        role_audience="public",
        category="general",
        prompt_text="What is IntelliChoice?",
        sort_order=0,
        active=True,
    ),
    ChatSuggestion(
        id="public-general-contact",
        role_audience="public",
        category="general",
        prompt_text="How do I get in touch with a branch?",
        sort_order=1,
        active=True,
    ),
    ChatSuggestion(
        id="public-branches-nearest",
        role_audience="public",
        category="branches",
        prompt_text="Which branch is nearest to me?",
        sort_order=2,
        active=True,
    ),
    ChatSuggestion(
        id="public-branches-hours",
        role_audience="public",
        category="branches",
        prompt_text="What are your branch hours?",
        sort_order=3,
        active=True,
    ),
    ChatSuggestion(
        id="public-calendar-upcoming",
        role_audience="public",
        category="calendar",
        prompt_text="What's coming up on the calendar?",
        sort_order=4,
        active=True,
    ),
    ChatSuggestion(
        id="public-volunteering-how",
        role_audience="public",
        category="volunteering",
        prompt_text="How can I volunteer with IntelliChoice?",
        sort_order=5,
        active=True,
    ),
    ChatSuggestion(
        id="public-participation-start",
        role_audience="public",
        category="student_participation",
        prompt_text="How does a student get started at IntelliChoice?",
        sort_order=6,
        active=True,
    ),
    ChatSuggestion(
        id="student-general-expect",
        role_audience="student",
        category="general",
        prompt_text="What should I know as a student?",
        sort_order=0,
        active=True,
    ),
    ChatSuggestion(
        id="parent-general-expect",
        role_audience="parent",
        category="general",
        prompt_text="What should I know as a parent?",
        sort_order=0,
        active=True,
    ),
    ChatSuggestion(
        id="parent-general-progress",
        role_audience="parent",
        category="general",
        prompt_text="How is my child's progress tracked?",
        sort_order=1,
        active=True,
    ),
    ChatSuggestion(
        id="tutor-general-responsibilities",
        role_audience="tutor",
        category="general",
        prompt_text="What are my responsibilities as a tutor?",
        sort_order=0,
        active=True,
    ),
    ChatSuggestion(
        id="tutor-general-escalation",
        role_audience="tutor",
        category="general",
        prompt_text="What's the escalation procedure for a difficult situation?",
        sort_order=1,
        active=True,
    ),
    ChatSuggestion(
        id="branch_manager-general-responsibilities",
        role_audience="branch_manager",
        category="general",
        prompt_text="What are branch manager responsibilities?",
        sort_order=0,
        active=True,
    ),
    ChatSuggestion(
        id="branch_manager-general-escalation",
        role_audience="branch_manager",
        category="general",
        prompt_text="How do I access internal escalation procedures?",
        sort_order=1,
        active=True,
    ),
]


async def seed_default_suggestions(session: AsyncSession) -> tuple[int, int]:
    """Returns `(created, updated)` - never "unchanged", since `ChatSuggestionRepository.
    upsert` always writes (this catalog is small hand-authored data, not worth a
    `content_hash` no-op check the way scraped org content needs one).
    """
    repo = ChatSuggestionRepository(session)
    created = updated = 0
    for suggestion in SEED_SUGGESTIONS:
        existing = await repo.get(suggestion.id)
        await repo.upsert(suggestion)
        if existing is None:
            created += 1
        else:
            updated += 1
    return created, updated
