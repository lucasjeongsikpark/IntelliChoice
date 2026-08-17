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
    # These two used to read "What should I know as a student/parent?", and the classifier
    # was right to refuse them: `clarification` means "in scope but too vague to route", and
    # an open-ended "what should I know" has no answerable shape. The defect was that the app
    # offered them. Measured on staging 2026-08-07 - clicking the student chip, the very
    # first suggestion a signed-in student sees, returned "Could you rephrase your question?"
    # whose own text then lists "student participation and learning" as something it can
    # help with. Reproduced twice: typed verbatim and clicked as a chip.
    #
    # Rewritten to name a thing the corpus actually documents (programs), which is the shape
    # the scope prompt routes to `document_qa`.
    ChatSuggestion(
        id="student-general-expect",
        role_audience="student",
        category="general",
        prompt_text="What programs can I join as a student?",
        sort_order=0,
        active=True,
    ),
    ChatSuggestion(
        id="parent-general-expect",
        role_audience="parent",
        category="general",
        prompt_text="What programs are available for my child?",
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
    # --- D-382: the pool was 14 rows, 7 of them visible to a guest ---------------
    #
    # Follow-up chips are drawn from this catalog by category, so a pool that small
    # returned the same three generic prompts after every answer - and, before the
    # client-side filter added in the same change, prompts the visitor had just used.
    #
    # **Every row below names a section that exists in `knowledge-content/manifests`.**
    # That is what makes a suggestion safe to show: tapping it has to produce an answer,
    # and the fastest way to break trust in a chip is to have it return "I don't have an
    # approved source for that yet". The audience column matches the document's own, so a
    # guest is never offered a question only a parent can have answered.
    # Grounded in "Privacy Notice".
    ChatSuggestion(
        id="public-general-privacy",
        role_audience="public",
        category="general",
        prompt_text="How is my information kept private?",
        sort_order=7,
        active=True,
    ),
    # Grounded in "AI Use Notice".
    ChatSuggestion(
        id="public-general-ai",
        role_audience="public",
        category="general",
        prompt_text="How does IntelliChoice use AI?",
        sort_order=8,
        active=True,
    ),
    # Grounded in "Enrollment FAQ".
    ChatSuggestion(
        id="public-general-enroll",
        role_audience="public",
        category="general",
        prompt_text="How do I enroll a student?",
        sort_order=9,
        active=True,
    ),
    # Grounded in "Our Team".
    ChatSuggestion(
        id="public-general-team",
        role_audience="public",
        category="general",
        prompt_text="Who runs IntelliChoice?",
        sort_order=10,
        active=True,
    ),
    # Grounded in "Branch Directory / Contact Guide".
    ChatSuggestion(
        id="public-branches-contact",
        role_audience="public",
        category="branches",
        prompt_text="How do I contact a particular branch?",
        sort_order=11,
        active=True,
    ),
    # Grounded in "Academic Calendar".
    ChatSuggestion(
        id="public-calendar-term",
        role_audience="public",
        category="calendar",
        prompt_text="When does the next term start?",
        sort_order=12,
        active=True,
    ),
    # Grounded in "Academic Calendar".
    ChatSuggestion(
        id="public-calendar-closures",
        role_audience="public",
        category="calendar",
        prompt_text="Are there any upcoming closures?",
        sort_order=13,
        active=True,
    ),
    # Grounded in "Volunteer Guide".
    ChatSuggestion(
        id="public-volunteering-role",
        role_audience="public",
        category="volunteering",
        prompt_text="What do volunteers actually do?",
        sort_order=14,
        active=True,
    ),
    # Grounded in "Volunteer Guide".
    ChatSuggestion(
        id="public-volunteering-start",
        role_audience="public",
        category="volunteering",
        prompt_text="How do I start volunteering?",
        sort_order=15,
        active=True,
    ),
    # Grounded in "Student Participation Guide".
    ChatSuggestion(
        id="public-participation-expect",
        role_audience="public",
        category="student_participation",
        prompt_text="What is expected of students who join?",
        sort_order=16,
        active=True,
    ),
    # Grounded in "Attendance Policy".
    ChatSuggestion(
        id="parent-participation-attend",
        role_audience="parent",
        category="student_participation",
        prompt_text="How is my child's attendance recorded?",
        sort_order=17,
        active=True,
    ),
    # Grounded in "Understanding Your Child's Learning Report".
    ChatSuggestion(
        id="parent-general-report",
        role_audience="parent",
        category="general",
        prompt_text="How do I read my child's learning report?",
        sort_order=18,
        active=True,
    ),
    # Grounded in "Code of Conduct".
    ChatSuggestion(
        id="student-general-conduct",
        role_audience="student",
        category="general",
        prompt_text="What are the rules I need to follow?",
        sort_order=19,
        active=True,
    ),
    # Grounded in "Learning Platform Guide".
    ChatSuggestion(
        id="student-general-platform",
        role_audience="student",
        category="general",
        prompt_text="How do I use the learning platform?",
        sort_order=20,
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
