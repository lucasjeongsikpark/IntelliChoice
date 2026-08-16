"""The graph-input types survive a checkpoint round-trip, and will say so when they stop.

**The warning this pins is real and unfixed** (D-356). Every `aget_tuple` on either app
emits:

    Deserializing unregistered type chat_api.graph.build.AskInput ...
    will be blocked in a future version

LangGraph's `JsonPlusSerializer` defaults `allowed_msgpack_modules` to `True`, which means
*warn and allow*. When that default flips - or when the library is upgraded past the
version that flips it - a checkpoint holding one of these inputs stops deserializing, and
that is not a warning any more: it is every live session on both apps failing to resume.

**Why the obvious fix is not applied here.** Passing an explicit allowlist looks like a
five-line change (`serde=JsonPlusSerializer(allowed_msgpack_modules=[...])` at the five
saver call sites). It is not: reading `_create_msgpack_ext_hook`, `allowed_modules is True`
is the warn-and-allow branch, and passing *any* list takes the else-branch, which **blocks
everything not in it**. So the change does not silence a warning - it converts the whole
serializer to an allowlist, and anything else the existing checkpoints contain that is not
in `SAFE_MSGPACK_TYPES` starts failing to deserialize on live sessions. Shipping that
without first enumerating what staging's checkpoints actually hold trades a warning for an
outage, which is the worse trade.

So this test does the half that is safe and useful now: it proves the input type round
trips today, and it fails the moment it stops - in CI, on a library bump, rather than on a
student's resume. `LANGGRAPH_STRICT_MSGPACK=true` is the environment flag that blocks
immediately and is how the real allowlist should be enumerated when someone takes that on.

**One type per app, and the split is not tidiness.** `learning_api.graph.build.EntryInput` has
the identical exposure and its own copy of this test lives in `apps/learning-api/tests`,
because chat-api does not declare learning-api as a dependency - importing across the seam
is a defect this suite has already committed once in the other direction (D-353) and it
passes locally, where one venv holds both.
"""

from chat_api.graph.build import AskInput
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer


def test_ask_input_survives_a_checkpoint_round_trip() -> None:
    """`AskInput` is checkpointed on every turn, so it must come back.

    Asserted on the *values*, not just the type: a serializer that returned a
    correctly-typed object with default fields would be silent data loss, and this project
    has been burned repeatedly by assertions that held while meaning nothing.
    """
    serde = JsonPlusSerializer()

    ask = AskInput(session_id="c-1", query="What are the Saturday hours?", escalate=True)
    restored = serde.loads_typed(serde.dumps_typed(ask))

    assert isinstance(restored, AskInput)
    assert restored.session_id == "c-1"
    assert restored.query == "What are the Saturday hours?"
    assert restored.escalate is True


def test_the_round_trip_carries_the_field_added_after_live_threads_existed() -> None:
    """`client_turn_id` (D-348) is the newest field on this input.

    A field added after live threads already exist is where a serializer change bites
    first: old checkpoints have no value for it and new ones do. Pinned separately so a
    failure names the field rather than the whole model.
    """
    serde = JsonPlusSerializer()

    ask = AskInput(session_id="c-2", query="Do you offer online tutoring?", client_turn_id="t-9")
    assert serde.loads_typed(serde.dumps_typed(ask)).client_turn_id == "t-9"

    # And the default, which is what a checkpoint written before D-348 deserializes to.
    older = AskInput(session_id="c-3", query="Where are you?")
    assert serde.loads_typed(serde.dumps_typed(older)).client_turn_id is None
