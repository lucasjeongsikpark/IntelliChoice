"""D-255's panel: two reviewers, unanimity to accept, fail closed on silence.

These pin the *decision rules*, not verdict quality. What the panel decides given readings is
deterministic and testable; whether those readings are any good is D-256's measurement and is
not re-litigated here.
"""

import asyncio

import pytest
from intellichoice_adapters.bedrock.gateway import ResilientBedrockGateway
from intellichoice_adapters.bedrock.mock_provider import MockBedrockProvider
from intellichoice_curriculum.review_panel import (
    PanelVerdict,
    ReviewerReading,
    merge_defects,
    review_panel,
)
from intellichoice_shared.bedrock import (
    AuthoredGeneratedItemResponse,
    BedrockTask,
    HintSolutionDefect,
    HintSolutionReviewResponse,
    SolutionResponse,
    SolutionStep,
)


def _item(**overrides: object) -> AuthoredGeneratedItemResponse:
    base: dict[str, object] = dict(
        stem="Solve for n: 4n = 52.",
        context_block=None,
        option_a="13",
        option_b="12",
        option_c="14",
        option_d="11",
        correct_option="a",
        equation="Eq(4*n, 52)",
        hint_ladder=[
            "What operation undoes multiplication?",
            "Both sides can be divided by the same number.",
            "Divide 52 by 4.",
        ],
        canonical_solution=SolutionResponse(
            steps=[
                SolutionStep(
                    step_number=1,
                    explanation="Divide both sides by 4",
                    expression="n = 52/4",
                ),
                SolutionStep(step_number=2, explanation="Simplify", expression="n = 13"),
            ],
            final_answer="13",
        ),
        estimated_time_seconds=60,
        proposed_difficulty=3,
        difficulty_rationale="One inverse operation, no negatives.",
    )
    base.update(overrides)
    return AuthoredGeneratedItemResponse(**base)  # type: ignore[arg-type]


def _response(
    verdict: str, defects: list[HintSolutionDefect] | None = None
) -> HintSolutionReviewResponse:
    return HintSolutionReviewResponse(
        verdict=verdict,  # type: ignore[arg-type]
        defects=defects or [],
        uncertainty="low",
        reasoning="r",
    )


def _defect(index: int | None = 1, target: str = "hint_ladder") -> HintSolutionDefect:
    return HintSolutionDefect(
        target=target,  # type: ignore[arg-type]
        index=index,
        problem="p",
        suggested_fix="f",
    )


def _gateway(task_model: str = "anthropic.claude-haiku-4-5") -> ResilientBedrockGateway:
    return ResilientBedrockGateway(
        provider=MockBedrockProvider(),
        model_registry={BedrockTask.HINT_SOLUTION_REVIEW: task_model},
    )


def test_acceptance_requires_every_reviewer_to_pass() -> None:
    both_pass = PanelVerdict(
        readings=[
            ReviewerReading("B", _response("pass")),
            ReviewerReading("C", _response("pass")),
        ]
    )
    assert both_pass.accepted

    one_repairs = PanelVerdict(
        readings=[
            ReviewerReading("B", _response("pass")),
            ReviewerReading("C", _response("repair", [_defect()])),
        ]
    )
    assert not one_repairs.accepted


def test_a_reviewer_that_returned_nothing_blocks_rather_than_consents() -> None:
    """§4.5b, and D-256 paid to find it: gpt-oss emitted `defects[0].index = 0` against
    `Field(ge=1)` and produced no verdict. Treating silence as agreement would make an
    outage read as approval, which is the failure CLAUDE.md rule 5 exists to forbid.
    """
    verdict = PanelVerdict(
        readings=[
            ReviewerReading("B", _response("pass")),
            ReviewerReading(
                "C", None, error="structured output still invalid after one repair retry"
            ),
        ]
    )
    assert not verdict.accepted
    assert verdict.unreachable == ["C"]


def test_an_empty_panel_is_not_an_acceptance() -> None:
    """Nobody looked, so nobody approved. The degenerate case of the same rule."""
    assert not PanelVerdict(readings=[]).accepted


def test_hallucinated_locations_are_dropped_and_reported_separately() -> None:
    """A defect pointing past the end of the ladder must not reach a repair prompt as if it
    were real - but it must not vanish either, because a reviewer inventing locations is
    itself a finding.
    """
    item = _item()
    readings = [
        ReviewerReading("B", _response("repair", [_defect(index=7), _defect(index=2)])),
        ReviewerReading("C", _response("pass")),
    ]
    usable, discarded = merge_defects(readings, item)
    assert [d.index for d in usable] == [2]
    assert discarded == ["B: hint_ladder[7] does not exist (hint_ladder has 3 entries)"]


def test_an_unlocated_defect_survives_the_filter() -> None:
    """`index=None` means "this is about the ladder as a whole", which is legitimate and
    common - the filter is for indices that point *past the end*, not for their absence.
    """
    usable, discarded = merge_defects(
        [ReviewerReading("B", _response("repair", [_defect(index=None)]))], _item()
    )
    assert len(usable) == 1 and discarded == []


def test_both_reviewers_naming_the_same_step_is_kept_twice() -> None:
    """Deliberate. Agreement between two independent reviewers is the strongest signal the
    panel produces, and deduplicating would erase exactly the thing that makes it strong.
    """
    usable, _ = merge_defects(
        [
            ReviewerReading("B", _response("repair", [_defect(index=2)])),
            ReviewerReading("C", _response("repair", [_defect(index=2)])),
        ],
        _item(),
    )
    assert [d.index for d in usable] == [2, 2]


def test_defects_from_a_silent_reviewer_contribute_nothing() -> None:
    usable, discarded = merge_defects(
        [
            ReviewerReading("B", None, error="boom"),
            ReviewerReading("C", _response("repair", [_defect(index=1)])),
        ],
        _item(),
    )
    assert [d.index for d in usable] == [1] and discarded == []


def test_the_panel_reads_the_item_with_every_reviewer_under_the_mock() -> None:
    async def run() -> None:
        verdict = await review_panel(
            {"B": _gateway(), "C": _gateway()},
            _item(),
            skill_name="linear_one_step",
            grade_band="6-8",
            session_spend_cents=0.0,
        )
        assert [r.reviewer for r in verdict.readings] == ["B", "C"]
        assert verdict.accepted
        assert verdict.defects == []

    asyncio.run(run())


def test_one_reviewer_blocking_is_enough_to_stop_the_item() -> None:
    """The mock emits a located `repair` when a rung repeats its predecessor verbatim, so
    both reviewers block here - what this pins is that the merged defects reach the caller
    with their locations intact, which is what a repair prompt needs.
    """

    async def run() -> None:
        verdict = await review_panel(
            {"B": _gateway(), "C": _gateway()},
            _item(hint_ladder=["Divide 52 by 4.", "Divide 52 by 4.", "What is 52/4?"]),
            skill_name="linear_one_step",
            grade_band="6-8",
            session_spend_cents=0.0,
        )
        assert not verdict.accepted
        assert [d.index for d in verdict.defects] == [2, 2]
        assert all(d.suggested_fix for d in verdict.defects)

    asyncio.run(run())


def test_a_raising_gateway_becomes_a_blocking_reading_not_an_exception() -> None:
    """The panel must survive one reviewer being down. If it propagated the exception, an
    outage in reviewer C would stop the batch instead of blocking the item - the same
    conflation of "cannot review" with "must not proceed" that §4.5b resolves the other way.
    """

    class _Broken:
        async def generate_structured(self, **_: object) -> object:
            raise RuntimeError("bedrock is down")

        async def embed(self, **_: object) -> object:  # pragma: no cover - unused
            raise NotImplementedError

    async def run() -> None:
        verdict = await review_panel(
            {"B": _gateway(), "C": _Broken()},  # type: ignore[dict-item]
            _item(),
            skill_name="linear_one_step",
            grade_band="6-8",
            session_spend_cents=0.0,
        )
        assert not verdict.accepted
        assert verdict.unreachable == ["C"]
        assert "bedrock is down" in (verdict.readings[1].error or "")

    asyncio.run(run())


@pytest.mark.parametrize("verdict", ["repair", "reject"])
def test_both_blocking_verdicts_stop_acceptance_identically(verdict: str) -> None:
    """§4.2: they differ in weight at the early-stop rule, never in destination."""
    panel = PanelVerdict(
        readings=[
            ReviewerReading("B", _response("pass")),
            ReviewerReading("C", _response(verdict, [_defect()])),
        ]
    )
    assert not panel.accepted
