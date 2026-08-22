"""D-351: every turn carries a reason code, and the words never restate the label.

Two properties, and the second is the one that was actually wrong in the field:

1. **Every outcome is classified.** A turn that produces an `answer` must produce a `reason`,
   so a client can branch on the cause instead of inferring it from `escalation_recommended`
   + `citations` + `access_hint` - three fields that merely correlate, and whose correlation
   is how AUD-C-19 shipped one message for three different causes.
2. **The user-facing copy is not the classifier label.** `out_of_scope` is a label; "I cannot
   answer unrelated general-purpose questions" is that label read at a parent asking how to
   get a mistaken donation refunded (measured live, D-343). And `ACCESS_REQUIRED` must not
   name the tier it found, because that tells an unauthenticated caller a restricted document
   exists.

The boundary cases at the bottom are the ones a taxonomy gets wrong: three refusals that look
alike to a reader and must not collapse into one code.
"""

import asyncio
import importlib
import pkgutil
from collections.abc import Mapping
from enum import Enum

import chat_api
import pytest
from chat_api.graph.nodes import OUT_OF_SCOPE_MESSAGE, SERVICE_UNAVAILABLE_MESSAGE
from chat_api.services import outcomes
from chat_api.services.outcomes import REASON_MESSAGES, TurnReason
from chat_api.services.role_access import ACCESS_HINT_MESSAGES

from .conftest import postgres_skip_reason, rollback_session
from .test_qa_graph import _ask, _DegradedGateway, _seed_chunk

pytestmark = pytest.mark.skipif(
    (_reason := postgres_skip_reason()) is not None, reason=_reason or ""
)


def _run(coro_factory) -> dict:
    async def run() -> dict:
        async with rollback_session() as session:
            return await coro_factory(session)

    return asyncio.run(run())


# --- the taxonomy itself, no database needed -----------------------------------------


def test_no_default_message_restates_its_own_classifier_label() -> None:
    """**The rule the whole entry exists for.** A visitor should never be able to read the
    internal category out of the prose.

    The pairing here is stricter than the sweep below - each default message against *its
    own* reason - and narrower: it sees the five entries of `REASON_MESSAGES` and nothing
    else. Its docstring used to claim "the next message added is covered by construction",
    which was true only for a message added *to the dict*; see
    `test_no_user_facing_copy_restates_a_reason_code` for the total version (F-09).
    """
    for reason, message in REASON_MESSAGES.items():
        label_words = reason.value.replace("_", " ")
        assert label_words not in message.lower(), (
            f"{reason.value}'s message contains its own label: {message!r}"
        )


# --- REQ-44 / F-09 / DRIFT-74: the sweep, made total ----------------------------------
# The test above ran green in a 43-test batch and the pass was necessary and not
# sufficient: it iterates only `REASON_MESSAGES` (5 entries) against a 10-value enum with a
# plain substring check, so it passes **vacuously for any copy defined outside the dict** -
# `UNAVAILABLE_INTENT_MESSAGES`, the `LOCATION_*` strings, `RATE_LIMITED_MESSAGE` and the
# calendar copy are all node-local, and a new message restating a reason code among them
# would have left the suite green.
#
# Not fixed by making `REASON_MESSAGES` exhaustive over the ten. The dict is the *default*
# copy for reasons that need words, and two reasons deliberately have none: `ANSWER`'s words
# are the answer, and a cancelled turn deliberately carries no answer at all (D-402 -
# "inventing any of them would put words in the transcript the visitor did not ask for").
# Exhaustiveness would invent copy for exactly the two reasons that must not have it. So:
# discover the copy instead, and pin the enum classification separately.

# Module-level strings that are **not** copy anyone reads: wire identifiers, scopes, a
# document id, a config default, and the one string here addressed to a *model* rather than
# to a visitor. Listed by qualified name rather than skipped by a naming convention on
# purpose - a convention silently misses the constant someone names badly, whereas an
# unlisted new constant is swept by default and a listed name that stops existing fails
# `test_the_copy_sweep_is_maintained`.
_NOT_USER_FACING_COPY = frozenset(
    {
        "chat_api.config.DEV_JWT_SECRET",
        "chat_api.graph.build.END",
        "chat_api.graph.build.START",
        "chat_api.graph.nodes.SCOPE_AND_INTENT_SYSTEM_PROMPT",
        "chat_api.main.SCOPE_CHAT_MESSAGE",
        "chat_api.routers.sessions.SCOPE_CHAT_TURN",
        "chat_api.routers.sessions.SUBJECT_CHAT_API",
        "chat_api.routers.stream.KEEPALIVE_FRAME",
        "chat_api.services.escalation_rate_limit.SCOPE_ADMIN_ESCALATION",
        "chat_api.services.role_access.PUBLIC_AUDIENCE",
        "chat_api.services.session_event_relay.CHANNEL",
        "chat_api.services.suggestions.GENERAL_CATEGORY",
        "chat_api.services.suggestions.PUBLIC_AUDIENCE",
        "chat_api.services.welcome.ORGANIZATION_OVERVIEW_DOCUMENT_ID",
    }
)

# `answer` is the one label string that is also ordinary English this product correctly
# says - "I can't answer that from the sources available to you" names no classification.
# It is the only exemption, it is evidence-driven rather than a judgement call (the sweep
# below asserts that real copy still forces it), and every other label is swept: eight of
# them are phrases nobody writes to a visitor by accident, and `cancelled` is exempted
# nowhere because no copy says it today.
_LABELS_ALSO_ORDINARY_ENGLISH = frozenset({TurnReason.ANSWER})
_SWEPT_LABELS = frozenset(TurnReason) - _LABELS_ALSO_ORDINARY_ENGLISH

# The other five of the ten, split by *why* they are not in `REASON_MESSAGES` - because
# "not in the dict" turns out to mean two different things, and collapsing them is what
# would make an exhaustiveness assertion invent copy for the wrong reasons.
#
# Every production site of these three sets a specific `answer` of its own, which is the
# pattern `REASON_MESSAGES`' own comment describes ("A node with a *more* specific message
# for the same reason keeps it"): `graph/nodes.py:454` and `:1172` (clarification, the
# missing-location prompt), `:777` and `:1156` (the escalation rate limit, a declined
# location), `:874` and `:1068` (the escalation and email paths).
_REASONS_WITH_NODE_LOCAL_COPY_ONLY = frozenset(
    {
        TurnReason.HUMAN_ACTION_REQUIRED,
        TurnReason.POLICY_RESTRICTED,
        TurnReason.NEEDS_CLARIFICATION,
    }
)
# And the two with no copy anywhere, deliberately.
_REASONS_WITH_NO_COPY_AT_ALL = frozenset({TurnReason.ANSWER, TurnReason.CANCELLED})


def _copy_strings(value: object) -> list[str]:
    """The string leaves of a module-level constant: a bare string, or the strings inside a
    mapping or sequence of them (`REASON_MESSAGES`, `ACCESS_HINT_MESSAGES`,
    `UNAVAILABLE_INTENT_MESSAGES`).

    `Enum` members are skipped even though a `StrEnum` member *is* a string: a `TurnReason`
    sitting in `ESCALATABLE` is the code itself, and sweeping it would fail trivially and
    tell a reader nothing.
    """
    if isinstance(value, Enum):
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        return [text for item in value.values() for text in _copy_strings(item)]
    if isinstance(value, list | tuple | set | frozenset):
        return [text for item in value for text in _copy_strings(item)]
    return []


def _discovered_strings() -> dict[str, list[str]]:
    """Every module-level string constant in the whole `chat_api` package, by qualified
    name. Walked rather than listed: a pinned module list is the same vacuity hole one level
    up, invisible the day copy lands in a new module.
    """
    discovered: dict[str, list[str]] = {}
    for module_info in pkgutil.walk_packages(chat_api.__path__, f"{chat_api.__name__}."):
        module = importlib.import_module(module_info.name)
        for name, value in vars(module).items():
            if name.startswith("_") or not name.isupper():
                continue
            texts = _copy_strings(value)
            if texts:
                discovered[f"{module_info.name}.{name}"] = texts
    return discovered


def _user_facing_copy() -> dict[str, list[str]]:
    return {
        name: texts
        for name, texts in _discovered_strings().items()
        if name not in _NOT_USER_FACING_COPY
    }


def _restated_labels(text: str) -> set[TurnReason]:
    lowered = text.lower()
    return {label for label in _SWEPT_LABELS if label.value.replace("_", " ") in lowered}


def test_the_copy_sweep_is_maintained() -> None:
    """The sweep's own positive control. "No copy restates a reason code" is worth exactly
    as much as the guarantee that the sweep looked at the copy - and every one of the four
    constant families the finding names by hand is asserted present, because those are the
    ones the old sweep could not see.
    """
    copy = _user_facing_copy()

    for expected in (
        "chat_api.graph.nodes.UNAVAILABLE_INTENT_MESSAGES",
        "chat_api.graph.nodes.LOCATION_DECLINED_MESSAGE",
        "chat_api.graph.nodes.LOCATION_MISSING_MESSAGE",
        "chat_api.graph.nodes.LOCATION_CONSENT_NOTICE",
        "chat_api.graph.nodes.RATE_LIMITED_MESSAGE",
        "chat_api.graph.nodes.CALENDAR_CANCELLED_MESSAGE",
        "chat_api.graph.nodes.CALENDAR_GOOGLE_FAILED_FALLBACK_MESSAGE",
        "chat_api.graph.nodes.NO_UPCOMING_EVENTS_MESSAGE",
        "chat_api.routers.sessions.TOO_MANY_TURNS_MESSAGE",
        "chat_api.services.outcomes.REASON_MESSAGES",
        "chat_api.services.role_access.ACCESS_HINT_MESSAGES",
        "chat_api.services.welcome.FALLBACK_WELCOME_TEXT",
    ):
        assert expected in copy, f"the copy sweep no longer sees {expected}"
    assert len(copy) >= 25, f"the sweep found only {len(copy)} constants - it stopped looking"

    stale = _NOT_USER_FACING_COPY - set(_discovered_strings())
    assert not stale, f"these exclusions no longer name anything: {sorted(stale)}"


def test_no_user_facing_copy_restates_a_reason_code() -> None:
    """**F-09's fix.** The rule now holds over every user-facing string in the app, wherever
    it is defined, instead of over the five entries that happen to live in `REASON_MESSAGES`.
    A message added anywhere that reads its own classifier label aloud fails here.
    """
    violations = {
        f"{name}: {text!r}": sorted(label.value for label in _restated_labels(text))
        for name, texts in _user_facing_copy().items()
        for text in texts
        if _restated_labels(text)
    }
    assert not violations, f"user-facing copy restates a reason code: {violations}"

    # The positive control. Without it, "no violations" is indistinguishable from "the
    # matcher never fires", which is the shape of the pass this test replaces.
    assert _restated_labels("Your question was classified as out of scope.") == {
        TurnReason.OUT_OF_SCOPE
    }
    # And the exemption is evidence-driven, not taste: it exists because correct copy really
    # does say the word. If that stops being true, drop the exemption rather than keeping it.
    assert any(
        "answer" in text.lower() for texts in _user_facing_copy().values() for text in texts
    ), "nothing says 'answer' any more - `ANSWER` no longer needs exempting from the sweep"


def test_every_reason_code_is_classified_for_where_its_copy_lives() -> None:
    """The second half of "five of ten": the sweep above is total over the *copy*, this is
    total over the *enum*. The ten reasons partition into exactly three buckets - default
    copy in `REASON_MESSAGES` (5), node-local copy only (3), no copy at all (2) - so adding
    a `TurnReason` fails here until someone says which it is, instead of landing silently
    outside every guard, which is how five of ten became the status quo.

    The three buckets are also why "just assert `REASON_MESSAGES` is exhaustive over the
    ten" is the wrong fix: it would demand default copy for `ANSWER`, whose words *are* the
    answer, and for `CANCELLED`, where `_cancelled_turn_fields` returns no answer at all on
    purpose (D-402 - "inventing any of them would put words in the transcript the visitor
    did not ask for").
    """
    buckets = {
        "REASON_MESSAGES": frozenset(REASON_MESSAGES),
        "node-local copy only": _REASONS_WITH_NODE_LOCAL_COPY_ONLY,
        "no copy at all": _REASONS_WITH_NO_COPY_AT_ALL,
    }
    classified = frozenset().union(*buckets.values())
    assert classified == set(TurnReason), (
        f"unclassified reason codes: {sorted(r.value for r in set(TurnReason) - classified)}"
    )
    for left, right in ((a, b) for a in buckets for b in buckets if a < b):
        overlap = buckets[left] & buckets[right]
        assert not overlap, (
            f"{sorted(r.value for r in overlap)} is in both {left!r} and {right!r} - a reason's "
            "copy lives in one place or the test says nothing about where"
        )


def test_the_out_of_scope_message_does_not_characterise_the_question() -> None:
    """The measured case (D-343): a parent asking about a donation refund was told the
    question was an "unrelated general-purpose" one. Donations are genuinely outside SPEC
    §5.19.4's topic list and D-351 deliberately did not add them - so the classification
    stands and only the description of the *asker's question* goes.
    """
    message = outcomes.OUT_OF_SCOPE_MESSAGE.lower()
    assert "unrelated" not in message
    assert "general-purpose" not in message
    # The actionable half stays: what this assistant does cover, and who to ask otherwise.
    assert "branches" in message and "volunteering" in message
    assert "branch" in message


def test_the_access_required_message_names_no_role_and_no_document() -> None:
    """`required_role` used to reach the caller as one of four role-specific sentences. That
    tells an unauthenticated caller which tier holds a document matching their terms - a
    disclosure made by a probe that runs only *because* the pipeline already declined, and one
    measured wrong in the field (AUD-C-25/D-179 named `parent` for a public-corpus answer).
    """
    message = outcomes.ACCESS_REQUIRED_MESSAGE.lower()
    for role in ("parent", "student", "tutor", "branch manager", "branch_manager"):
        assert role not in message, f"the access-required copy names the {role!r} tier"
    # It still says the one useful thing.
    assert "sign in" in message


def test_the_old_role_specific_hints_are_no_longer_reachable_copy() -> None:
    """`ACCESS_HINT_MESSAGES` still exists - `build_access_hint` selects an audience and the
    selection is logged and measured (D-351's instrument). What must not happen is one of
    those strings reaching a caller again by a later edit re-wiring `answer` to `hint.message`.
    """
    for role_message in ACCESS_HINT_MESSAGES.values():
        assert role_message != outcomes.ACCESS_REQUIRED_MESSAGE
        assert role_message not in outcomes.ACCESS_REQUIRED_MESSAGE


def test_every_reason_that_offers_a_human_is_declared_escalatable() -> None:
    """`ESCALATABLE` is documentation that has to stay true: a reason whose copy promises to
    pass the question to a person, but which is not in the set, is a promise nothing tracks.
    """
    for reason in outcomes.ESCALATABLE:
        message = REASON_MESSAGES[reason].lower()
        assert "branch" in message, f"{reason.value} is escalatable but offers no human"


# --- the graph, end to end ------------------------------------------------------------


def test_an_out_of_scope_question_is_classified_and_worded_separately() -> None:
    result = _run(
        lambda session: _ask(
            session,
            claims=None,
            query="What's the best recipe for chocolate chip cookies?",
            thread_id="t-reason-out-of-scope",
        )
    )
    assert result["reason"] == TurnReason.OUT_OF_SCOPE
    assert result["answer"] == OUT_OF_SCOPE_MESSAGE


def test_a_grounded_answer_is_classified_as_an_answer() -> None:
    async def ask(session):
        await _seed_chunk(
            session, audience="public", chunk_text="Branches open 9am to 1pm on Saturdays."
        )
        return await _ask(
            session,
            claims=None,
            query="What are the Saturday hours?",
            thread_id="t-reason-answer",
        )

    result = _run(ask)
    assert result["reason"] == TurnReason.ANSWER
    assert result["citations"]


def test_an_outage_is_a_system_error_not_a_statement_about_the_question() -> None:
    """AUD-C-07/AUD-C-08 in taxonomy form. The reason must separate "we broke" from "we do
    not know" - which, before a reason code existed, only the message text distinguished.
    """

    async def ask(session):
        await _seed_chunk(session, audience="public", chunk_text="Saturday hours are 9 to 1.")
        return await _ask(
            session,
            claims=None,
            query="What are the Saturday hours?",
            thread_id="t-reason-degraded",
            gateway=_DegradedGateway(),
        )

    result = _run(ask)
    assert result["reason"] == TurnReason.SYSTEM_ERROR
    assert result["answer"] == SERVICE_UNAVAILABLE_MESSAGE
    assert result["reason"] != TurnReason.OUT_OF_SCOPE
    assert result["reason"] != TurnReason.NO_APPROVED_SOURCE


def test_a_supported_topic_with_no_source_is_not_out_of_scope() -> None:
    """**Boundary case 1.** These two are the pair most easily conflated: both refuse, both
    offer a human. The difference is whether the *topic* is supported, and it decides whether
    the honest next step is "ask someone" or "ask something else".
    """
    result = _run(
        lambda session: _ask(
            session,
            claims=None,
            query="zqxvchunk handbook",
            thread_id="t-reason-no-source",
        )
    )
    assert result["reason"] == TurnReason.NO_APPROVED_SOURCE
    assert result["escalation_recommended"] is True


def test_a_role_gated_match_is_access_required_not_no_approved_source() -> None:
    """**Boundary case 2**, and the one D-343 measured going wrong for a real visitor. The
    corpus *does* answer this - just not for this caller - so "I don't have an approved
    source" is false in a way the caller can act on if told the truth.

    Skipped rather than faked when the probe's reranker arm cannot run: `MockBedrockProvider`
    emits hash-vector embeddings, so `probe_access` falls to its lexical arm (D-165), and
    whether that arm fires for a given fixture is a property of the fixture's wording rather
    than of the code under test. Asserting on it would be asserting on the fixture.
    """

    async def ask(session):
        await _seed_chunk(
            session,
            audience="parent",
            chunk_text=(
                "Attendance policy: if a student is marked absent for the week the platform "
                "blocks that week's session until the branch manager reviews it."
            ),
        )
        return await _ask(
            session,
            claims=None,
            query="attendance policy absent week blocks session",
            thread_id="t-reason-access",
        )

    result = _run(ask)
    if result["reason"] != TurnReason.ACCESS_REQUIRED:
        pytest.skip(
            "the access probe took its lexical arm and found nothing - unreachable offline "
            f"(D-165); got reason={result['reason']!r}"
        )
    assert result["answer"] == outcomes.ACCESS_REQUIRED_MESSAGE
    # The tier is still selected in state - that is what keeps the probe measurable - and is
    # dropped by `AccessHintResponse` at the API boundary.
    assert result["access_hint"]["message"] == outcomes.ACCESS_REQUIRED_MESSAGE
    assert result["access_hint"]["required_role"] in {
        "parent",
        "student",
        "tutor",
        "branch_manager",
    }
    assert "parent" not in result["answer"].lower()


def test_the_reason_does_not_survive_into_the_next_turn() -> None:
    """AUD-C-04's class, applied to the new field: a reason left set by a refusal would label
    the next turn's answer with the previous turn's cause. The reset lives in `resolve_role`
    with the other per-turn fields precisely so a new field cannot be forgotten.
    """

    async def two_turns(session):
        graph_thread = "t-reason-carryover"
        await _ask(
            session,
            claims=None,
            query="What's the best recipe for chocolate chip cookies?",
            thread_id=graph_thread,
        )
        await _seed_chunk(
            session, audience="public", chunk_text="Branches open 9am to 1pm on Saturdays."
        )
        return await _ask(
            session,
            claims=None,
            query="What are the Saturday hours?",
            thread_id=graph_thread,
        )

    result = _run(two_turns)
    assert result["reason"] != TurnReason.OUT_OF_SCOPE


def test_the_api_response_carries_the_reason_and_not_the_tier() -> None:
    """**The boundary assertion**, and the reason `required_role` can safely stay in state.

    Everything above tests the graph. This tests the seam: `AccessHintResponse` is built
    field by field precisely so the tier cannot ride along, and a future `**access_hint`
    would silently undo that. Driven through `TestClient` rather than by reading the model,
    because the model is what would be edited.
    """
    from chat_api.main import app
    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        session_id = client.post("/chat/sessions").json()["chat_session_id"]
        body = client.post(
            f"/chat/sessions/{session_id}/messages",
            json={"query": "What's the best recipe for chocolate chip cookies?"},
        ).json()

    assert body["reason"] == TurnReason.OUT_OF_SCOPE
    assert "unrelated" not in (body["answer"] or "").lower()
    # `access_hint` is null on this path; the shape guarantee is what matters, so it is
    # asserted against the response *model* rather than only against this one payload.
    from chat_api.routers.sessions import AccessHintResponse

    assert set(AccessHintResponse.model_fields) == {"message"}, (
        "AccessHintResponse grew a field - if that field names a role or a document, it is "
        "the disclosure D-351 removed"
    )
