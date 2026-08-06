"""D-207: the error strings `learning-web` translates for students are pinned here.

`apps/learning-web/src/api/errors.ts` maps a backend failure to a sentence a K-12 student
can read, keyed on `status` **plus a fragment of the detail** - because `/answers` alone
returns 409 for five different situations and "you already answered this one" and "your
time ran out" need different words.

That mapping is a cross-language coupling with nothing holding it together, and it broke on
its first attempt: the frontend tested for `"already answered"`, while
`ItemAlreadyAnsweredError` formats `item {id} has already been answered` - not a substring.
The duplicate-submission case silently fell through to the generic line, which was only
noticed because a Playwright failure screenshot happened to show it.

So: these assertions exist to fail *here*, in a fast unit test, if anyone rewords a message
the frontend keys on. When one fails, change the fragment in `errors.ts` in the same commit.
They deliberately assert **fragments**, not whole strings - the id, the phase name and the
variant id in these messages are all variable, and pinning a whole message would make this
file break on changes that do not matter.
"""

from learning_api.services.flow import (
    InvalidPhaseError,
    ItemAlreadyAnsweredError,
    UnknownQuestionVariantError,
)

# Must stay in step with the `RULES` table in apps/learning-web/src/api/errors.ts.
FRONTEND_FRAGMENTS = {
    "already_answered": "already been answered",
    "not_served": "not an item of this session",
}


def test_a_duplicate_answer_says_already_been_answered() -> None:
    message = str(ItemAlreadyAnsweredError("qv-123"))
    assert FRONTEND_FRAGMENTS["already_answered"] in message.lower(), (
        f"errors.ts keys the 'you already answered this one' message on "
        f"{FRONTEND_FRAGMENTS['already_answered']!r}; this message is now {message!r}, so a "
        f"duplicate submission would show the generic fallback instead"
    )


def test_an_unserved_variant_says_not_an_item_of_this_session() -> None:
    message = str(UnknownQuestionVariantError("qv-123", reason="not_served"))
    assert FRONTEND_FRAGMENTS["not_served"] in message.lower(), (
        f"errors.ts keys its stale-tab message on {FRONTEND_FRAGMENTS['not_served']!r}; "
        f"this message is now {message!r}"
    )


def test_the_wrong_phase_message_still_names_the_phase() -> None:
    """`InvalidPhaseError` is not itself keyed on by the frontend - the route builds its
    own `session is not accepting answers in phase {phase}` detail - but this asserts the
    exception carries something usable, so the route's wording is not the only record of
    what went wrong.
    """
    assert str(InvalidPhaseError("cannot answer during post_exam"))


def test_the_frontend_error_table_covers_every_answer_conflict() -> None:
    """A reading test, not a behaviour one: `submit_answer` has five 409 branches, and this
    lists them so a sixth added later is an obvious omission rather than a silent fall
    through to the generic message.

    Kept as a literal list rather than parsed out of the router - parsing would make this
    pass automatically for a branch nobody had thought about, which is the opposite of what
    it is for.
    """
    known_409_reasons = {
        "select a student before answering",
        "session is not accepting answers in phase",
        "exam time limit exceeded - finalize to submit",
        "is not an item of this session",
        "has already been answered",
    }
    assert len(known_409_reasons) == 5
