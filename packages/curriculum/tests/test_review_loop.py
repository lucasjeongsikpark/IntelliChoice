"""D-260's loop: panel → repair → panel, bounded four ways, then discard.

The four bounds are the point of these tests, because each one exists to stop a different
runaway: the round limit, the per-item spend cap, the recurring-defect stop, and "a block with
nothing to repair against".
"""

import asyncio

import pytest
from intellichoice_adapters.bedrock.gateway import ResilientBedrockGateway
from intellichoice_adapters.bedrock.mock_provider import MockBedrockProvider
from intellichoice_curriculum.hint_solution_repair import (
    SYSTEM_PROMPT,
    apply_repair,
    build_payload,
    collateral_edits,
    render_defects,
)
from intellichoice_curriculum.review_loop import run_review_loop
from intellichoice_shared.bedrock import (
    AuthoredGeneratedItemResponse,
    BedrockTask,
    HintSolutionDefect,
    HintSolutionRepairResponse,
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
        hint_ladder=["What undoes multiplication?", "Divide both sides.", "Divide 52 by 4."],
        canonical_solution=SolutionResponse(
            steps=[
                SolutionStep(step_number=1, explanation="Divide by 4", expression="n = 52/4"),
                SolutionStep(step_number=2, explanation="Simplify", expression="n = 13"),
            ],
            final_answer="13",
        ),
        estimated_time_seconds=60,
        proposed_difficulty=3,
        difficulty_rationale="One inverse operation.",
    )
    base.update(overrides)
    return AuthoredGeneratedItemResponse(**base)  # type: ignore[arg-type]


def _gateway() -> ResilientBedrockGateway:
    return ResilientBedrockGateway(
        provider=MockBedrockProvider(),
        model_registry={
            BedrockTask.HINT_SOLUTION_REVIEW: "anthropic.claude-haiku-4-5",
            BedrockTask.HINT_SOLUTION_REPAIR: "anthropic.claude-haiku-4-5",
        },
    )


def _run(**kwargs: object):
    defaults: dict[str, object] = dict(
        reviewers={"B": _gateway(), "C": _gateway()},
        repairer=_gateway(),
        item=_item(),
        skill_name="linear_one_step",
        grade_band="6-8",
        per_item_budget_cents=50.0,
    )
    defaults.update(kwargs)
    return asyncio.run(run_review_loop(**defaults))  # type: ignore[arg-type]


def test_a_clean_item_is_accepted_in_one_round_with_no_repair() -> None:
    outcome = _run()
    assert outcome.status == "accepted"
    assert outcome.stopped_because == "unanimous pass"
    assert len(outcome.rounds) == 1
    assert outcome.rounds[0].repaired_hint_ladder is None


def test_a_repairable_item_is_repaired_and_then_accepted() -> None:
    """The mock blocks a rung that repeats its predecessor and its repairer rewrites exactly
    that, so this exercises panel → repair → panel end to end for free.
    """
    outcome = _run(item=_item(hint_ladder=["Divide 52 by 4.", "Divide 52 by 4.", "What is 52/4?"]))
    assert outcome.status == "accepted"
    assert len(outcome.rounds) == 2
    assert outcome.rounds[0].defects and not outcome.rounds[1].defects
    # The repair is targeted: the rung nobody objected to is unchanged.
    assert outcome.item.hint_ladder[0] == "Divide 52 by 4."
    assert outcome.item.hint_ladder[1] != outcome.item.hint_ladder[0]


def test_the_repair_never_touches_the_stem_options_or_answer_key() -> None:
    """§4.6, enforced by `HintSolutionRepairResponse` having no such fields rather than by
    the prompt asking nicely. If a repair could move the answer key, the next panel would be
    reviewing a different question from the one that was measured.
    """
    original = _item(hint_ladder=["Divide 52 by 4.", "Divide 52 by 4.", "What is 52/4?"])
    outcome = _run(item=original)
    assert outcome.item.stem == original.stem
    assert outcome.item.correct_option == original.correct_option
    assert outcome.item.option_a == original.option_a
    assert outcome.item.equation == original.equation


def test_the_per_item_budget_stops_the_loop_before_the_round_limit() -> None:
    """§7: a round limit is not a spend limit. An earlier draft of this loop checked a
    running total that nothing incremented, so the cap could never fire - which is why this
    test asserts the *reason*, not merely that the loop ended.
    """
    outcome = _run(
        item=_item(hint_ladder=["Divide 52 by 4.", "Divide 52 by 4.", "What is 52/4?"]),
        per_item_budget_cents=0.0,
    )
    assert outcome.status == "discarded"
    assert outcome.stopped_because == "per-item budget reached"
    assert outcome.rounds == []


def test_spend_accumulates_across_rounds() -> None:
    outcome = _run(item=_item(hint_ladder=["Divide 52 by 4.", "Divide 52 by 4.", "What is 52/4?"]))
    assert outcome.spend_cents > 0


def test_an_unrepairable_item_is_discarded_at_the_round_limit() -> None:
    """A repairer that changes nothing is the worst case the round limit exists for. Here the
    recurring-defect stop catches it first, which is the intended order: it is strictly
    cheaper, and both end in a discard.
    """

    class _NoOpRepairer:
        async def generate_structured(self, **kwargs: object):
            item = kwargs["payload"]
            return type(
                "R",
                (),
                {
                    "value": HintSolutionRepairResponse(
                        reasoning="I changed nothing",
                        hint_ladder=list(item.hint_ladder),  # type: ignore[attr-defined]
                        solution_steps=[
                            SolutionStep(step_number=1, explanation="x", expression="y")
                        ],
                        solution_final_answer="13",
                    ),
                    "cost_cents": 1.0,
                },
            )()

        async def embed(self, **_: object):  # pragma: no cover - unused
            raise NotImplementedError

    outcome = _run(
        item=_item(hint_ladder=["Divide 52 by 4.", "Divide 52 by 4.", "What is 52/4?"]),
        repairer=_NoOpRepairer(),
    )
    assert outcome.status == "discarded"
    assert outcome.stopped_because == "same defects recurred"


def test_a_repairer_that_raises_discards_the_item_rather_than_the_batch() -> None:
    class _Broken:
        async def generate_structured(self, **_: object):
            raise RuntimeError("repairer is down")

        async def embed(self, **_: object):  # pragma: no cover - unused
            raise NotImplementedError

    outcome = _run(
        item=_item(hint_ladder=["Divide 52 by 4.", "Divide 52 by 4.", "What is 52/4?"]),
        repairer=_Broken(),
    )
    assert outcome.status == "discarded"
    assert outcome.stopped_because == "repair failed"
    assert "repairer is down" in (outcome.rounds[0].repair_error or "")


def test_a_silent_reviewer_discards_rather_than_consents() -> None:
    """§4.5b through the loop: unanimity is undefined when a reviewer says nothing, and the
    loop must not repair against a block it has no located defect for.
    """

    class _Silent:
        async def generate_structured(self, **_: object):
            raise RuntimeError("no verdict")

        async def embed(self, **_: object):  # pragma: no cover - unused
            raise NotImplementedError

    outcome = _run(reviewers={"B": _gateway(), "C": _Silent()})
    assert outcome.status == "discarded"
    assert outcome.stopped_because == "blocked with no usable defect"
    assert outcome.rounds[0].unreachable == ["C"]


def test_the_evidence_dict_survives_without_this_module() -> None:
    """D-195: a discard that consumed up to 17 calls has to be readable afterwards, and it
    goes in the existing `stage_results` JSON column rather than a new table.
    """
    import json

    outcome = _run(item=_item(hint_ladder=["Divide 52 by 4.", "Divide 52 by 4.", "What is 52/4?"]))
    evidence = outcome.as_evidence()
    assert json.loads(json.dumps(evidence))["status"] == "accepted"
    first = evidence["rounds"][0]
    assert first["verdicts"] == {"B": "repair", "C": "repair"}
    # The reviewer's own wording is recorded beside the repair, so verbatim adoption is
    # countable later rather than argued about now.
    assert first["suggested_fixes"] and first["repaired_hint_ladder"]


def test_defects_render_with_their_location_first() -> None:
    lines = render_defects(
        [
            HintSolutionDefect(target="hint_ladder", index=2, problem="p", suggested_fix="f"),
            HintSolutionDefect(
                target="canonical_solution", index=None, problem="q", suggested_fix="g"
            ),
        ]
    )
    assert lines[0].startswith("hint_ladder[2]: p")
    assert lines[1].startswith("canonical_solution (overall): q")


def test_the_repair_prompt_forbids_moving_the_answer_and_the_house_style() -> None:
    assert "are fixed and are not yours to change" in SYSTEM_PROMPT.replace("\n", " ")
    assert "there is no house style here" in SYSTEM_PROMPT
    assert "not as replacement text to paste in" in SYSTEM_PROMPT


def test_the_repair_payload_carries_at_least_one_defect() -> None:
    """`min_length=1`: a repair prompt with no defects is a re-roll (§4.6)."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        build_payload(_item(), [], skill_name="s", grade_band="6-8")


def test_apply_repair_replaces_only_the_ladder_and_the_solution() -> None:
    item = _item()
    repaired = apply_repair(
        item,
        HintSolutionRepairResponse(
            reasoning="r",
            hint_ladder=["one", "two"],
            solution_steps=[SolutionStep(step_number=1, explanation="e", expression="x")],
            solution_final_answer="13",
        ),
    )
    assert repaired.hint_ladder == ["one", "two"]
    assert len(repaired.canonical_solution.steps) == 1
    assert repaired.stem == item.stem and repaired.option_b == item.option_b


def test_collateral_edits_names_positions_no_defect_asked_about() -> None:
    """D-261's invariant. Measured need: `mistral-large-3` rewrote every solution step on
    4 of 4 attempts while correctly fixing the one it was asked about, so targeting is a
    model property rather than a guarantee and a prompt clause cannot enforce it.
    """
    item = _item()
    defect = HintSolutionDefect(
        target="hint_ladder", index=3, problem="p", suggested_fix="f"
    )
    # Rung 3 was named; rung 1 was not.
    repair = HintSolutionRepairResponse(
        reasoning="r",
        hint_ladder=["REWRITTEN", "Divide both sides.", "Divide 52 by 4 to finish."],
        solution_steps=list(item.canonical_solution.steps),
        solution_final_answer="13",
    )
    assert collateral_edits(item, repair, [defect]) == [
        "hint_ladder[1] changed but no defect named it"
    ]


def test_editing_a_named_position_is_not_collateral() -> None:
    item = _item()
    defect = HintSolutionDefect(
        target="hint_ladder", index=1, problem="p", suggested_fix="f"
    )
    repair = HintSolutionRepairResponse(
        reasoning="r",
        hint_ladder=["REWRITTEN", "Divide both sides.", "Divide 52 by 4."],
        solution_steps=list(item.canonical_solution.steps),
        solution_final_answer="13",
    )
    assert collateral_edits(item, repair, [defect]) == []


def test_an_unlocated_defect_puts_its_whole_target_in_scope() -> None:
    """`index=None` means "this is about the ladder as a whole", so nothing in that ladder
    is collateral - otherwise the only actionable response to such a defect would be
    reported as a violation.
    """
    item = _item()
    defect = HintSolutionDefect(
        target="hint_ladder", index=None, problem="p", suggested_fix="f"
    )
    repair = HintSolutionRepairResponse(
        reasoning="r",
        hint_ladder=["all", "three", "rewritten"],
        solution_steps=list(item.canonical_solution.steps),
        solution_final_answer="13",
    )
    assert collateral_edits(item, repair, [defect]) == []


def test_a_length_change_is_not_reported_as_collateral() -> None:
    """Adding a step can be a legitimate repair, and once the lengths differ, positions no
    longer align - any comparison would be inventing a correspondence rather than checking
    one. The caller still sees the length change itself.
    """
    item = _item()
    defect = HintSolutionDefect(
        target="canonical_solution", index=2, problem="p", suggested_fix="f"
    )
    repair = HintSolutionRepairResponse(
        reasoning="r",
        hint_ladder=list(item.hint_ladder),
        solution_steps=[
            SolutionStep(step_number=1, explanation="different", expression="also different"),
        ],
        solution_final_answer="13",
    )
    assert collateral_edits(item, repair, [defect]) == []


def test_a_repair_that_edits_unnamed_text_discards_rather_than_being_applied() -> None:
    """A rejected repair is not a rejected item: the loop stops and the item keeps the text
    it came in with, rather than the panel silently reviewing edits it never asked for.
    """

    class _OverreachingRepairer:
        async def generate_structured(self, **kwargs: object):
            payload = kwargs["payload"]
            ladder = list(payload.hint_ladder)  # type: ignore[attr-defined]
            ladder[0] = "a rung nobody complained about"
            return type(
                "R",
                (),
                {
                    "value": HintSolutionRepairResponse(
                        reasoning="I rewrote more than I was asked to",
                        hint_ladder=ladder,
                        solution_steps=[
                            SolutionStep(step_number=1, explanation="e", expression="x")
                        ],
                        solution_final_answer="13",
                    ),
                    "cost_cents": 1.0,
                },
            )()

        async def embed(self, **_: object):  # pragma: no cover - unused
            raise NotImplementedError

    original = _item(hint_ladder=["Divide 52 by 4.", "Divide 52 by 4.", "What is 52/4?"])
    outcome = _run(item=original, repairer=_OverreachingRepairer())
    assert outcome.status == "discarded"
    assert outcome.stopped_because == "repair edited unnamed text"
    assert outcome.rounds[0].collateral_edits
    assert outcome.item.hint_ladder == original.hint_ladder


def test_a_contributed_defect_opens_the_repair_path_the_panel_would_have_skipped() -> None:
    """D-263. D-262 measured the panel passing 5 of 10 items carrying a defect a free check
    finds every time. A contributor buys those items one repair attempt.
    """
    contributed = HintSolutionDefect(
        target="canonical_solution",
        index=2,
        problem="the last step does not state the answer",
        suggested_fix="show the result of the operation",
    )
    outcome = _run(first_round_defects=[contributed])
    # The clean fixture would have been accepted at round 1 with no repair.
    assert len(outcome.rounds) >= 2
    assert "canonical_solution[2]" in " ".join(outcome.rounds[0].defects)


def test_a_contributed_defect_can_never_reject_an_item() -> None:
    """The property that keeps this from becoming the gate D-257 forbade: from round 2 the
    panel alone decides, so a false positive costs one repair round rather than an item.
    """
    outcome = _run(
        first_round_defects=[
            HintSolutionDefect(
                target="canonical_solution",
                index=2,
                problem="a false positive",
                suggested_fix="nothing is actually wrong",
            )
        ]
    )
    assert outcome.status == "accepted"
    assert outcome.stopped_because == "unanimous pass"


def test_contributed_defects_apply_to_the_first_round_only() -> None:
    """If they persisted, a heuristic could hold an item blocked to the round limit - which
    is exactly the gate D-257 said its audit must never become.
    """
    outcome = _run(
        first_round_defects=[
            HintSolutionDefect(
                target="canonical_solution", index=2, problem="p", suggested_fix="f"
            )
        ]
    )
    assert len(outcome.rounds) == 2
    assert outcome.rounds[1].defects == []


def test_the_panel_still_decides_acceptance_when_a_defect_was_contributed() -> None:
    """A contributed defect buys an attempt, never an approval. With a repairer that changes
    nothing and a panel that blocks on its own, the item is still discarded.
    """

    class _NoOpRepairer:
        async def generate_structured(self, **kwargs: object):
            payload = kwargs["payload"]
            return type(
                "R",
                (),
                {
                    "value": HintSolutionRepairResponse(
                        reasoning="unchanged",
                        hint_ladder=list(payload.hint_ladder),  # type: ignore[attr-defined]
                        solution_steps=[
                            SolutionStep(step_number=1, explanation="e", expression="x")
                        ],
                        solution_final_answer="13",
                    ),
                    "cost_cents": 1.0,
                },
            )()

        async def embed(self, **_: object):  # pragma: no cover - unused
            raise NotImplementedError

    outcome = _run(
        item=_item(hint_ladder=["Divide 52 by 4.", "Divide 52 by 4.", "What is 52/4?"]),
        repairer=_NoOpRepairer(),
        first_round_defects=[
            HintSolutionDefect(
                target="canonical_solution", index=2, problem="p", suggested_fix="f"
            )
        ],
    )
    assert outcome.status == "discarded"
