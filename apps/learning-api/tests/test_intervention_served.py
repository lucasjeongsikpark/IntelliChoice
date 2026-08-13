"""The §5.11.6 "did this intervention serve anything" predicate, and why it is one
function.

Three call sites record support for one student action - `intervention_choice` (the button
panel's durable flags, `SUPPORT_USAGE`, and the `intervention_chosen` memory event), the
tutor chat's `request_video`/`request_solution` branch, and `App.tsx`'s client-side count
that the results screen shows. All three used to key on *what the student asked for*, so a
"Watch a video" that found no catalog row was recorded as video support on a path 108 of
112 skills take. ARCHITECTURE's gate-consistency invariant is why the fix is a shared
predicate rather than three matching conditions.

No Postgres, no graph, no fixtures on purpose: this is the pure decision, and it must stay
provable without the environment that makes the flow test's video branch data-dependent
(the lesson D-307 charged to two other tests). `test_video_catalog.py` owns the catalog
half; `test_learning_flow.py` owns the wiring.
"""

from learning_api.graph.nodes import _intervention_served, _showing_unavailable_video

# The two shapes `_video_intervention` actually returns, copied field-for-field rather than
# built by a helper - a helper shared with the code under test would hide a change to
# either shape, which is the whole thing these tests are here to notice.
SERVED_VIDEO = {
    "type": "video",
    "video_title": "Multiplying fractions",
    "video_url": "https://www.youtube.com/watch?v=zqxvvc",
    "video_source": "Some Channel",
}
UNAVAILABLE_VIDEO = {
    "type": "video",
    "message": (
        "A verified video is not currently available for this skill. You may choose a hint "
        "or step-by-step solution instead."
    ),
}
HINT = {"type": "hint", "hint_text": "Try combining the side lengths.", "hint_level": 1}
SOLUTION = {"type": "solution", "steps": [], "final_answer": "1/2"}


def test_a_catalog_video_counts_as_served() -> None:
    assert _intervention_served(SERVED_VIDEO) is True


def test_the_fallback_message_alone_does_not_count_as_served() -> None:
    """The defect this predicate exists for: §5.11.6's message is what a student sees when
    the catalog has nothing, and it is not video support.
    """
    assert _intervention_served(UNAVAILABLE_VIDEO) is False


def test_hints_and_solutions_always_count_as_served() -> None:
    """Only the video path can reach a student with nothing - `_hint_round` and the
    solution branch either return content or raise. A predicate that started returning
    False for these would silently stop recording the support that *did* arrive, which is
    the mirror image of the bug and worse.
    """
    assert _intervention_served(HINT) is True
    assert _intervention_served(SOLUTION) is True


def test_no_intervention_at_all_is_not_served() -> None:
    """The "continue"/no-choice round, where `last_intervention` stays None."""
    assert _intervention_served(None) is False


def test_served_is_keyed_on_the_video_not_on_the_message_text() -> None:
    """Rewording §5.11.6 must not turn an unserved video into a served one, and a served
    video that happens to carry a message must not become unserved. Both directions,
    because keying on `"message" in content` would pass the first and fail the second.
    """
    reworded = {"type": "video", "message": "No video yet - try a hint."}
    assert _intervention_served(reworded) is False
    assert _intervention_served({**SERVED_VIDEO, "message": "here you go"}) is True
    assert _intervention_served({"type": "video", "video_url": ""}) is False
    assert _intervention_served({"type": "video", "video_url": None}) is False


def test_showing_unavailable_video_separates_none_from_served_nothing() -> None:
    """The distinction that bounds the pause-reopen, and the one I got wrong first.

    `not _intervention_served(content)` is also true for `None`, so using it as the bound
    would refuse to reopen the pause on a student's *first* video request - exactly the
    case the reopen exists for. These two facts must stay separable.
    """
    assert _showing_unavailable_video(UNAVAILABLE_VIDEO) is True
    assert _showing_unavailable_video(None) is False
    assert _showing_unavailable_video(SERVED_VIDEO) is False
    assert _showing_unavailable_video(HINT) is False
