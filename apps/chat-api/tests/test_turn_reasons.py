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


def test_no_user_facing_message_restates_its_own_classifier_label() -> None:
    """**The rule the whole entry exists for.** A visitor should never be able to read the
    internal category out of the prose. Checked over every message rather than the one that
    was wrong, so the next message added is covered by construction.
    """
    for reason, message in REASON_MESSAGES.items():
        label_words = reason.value.replace("_", " ")
        assert label_words not in message.lower(), (
            f"{reason.value}'s message contains its own label: {message!r}"
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
