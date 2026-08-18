"""Two reviewers on every item, unanimity to accept (D-255, measured in D-256).

**Nothing calls this yet, and that is deliberate** - the same position `hint_solution_review`
was left in by D-251. This module is the panel step of
[HINT_SOLUTION_REVIEW.md](../../../../docs/HINT_SOLUTION_REVIEW.md) §4; the repair loop, the
round history and the discard path are not built.

What it does own, because each is a rule that would otherwise be re-derived at every call site:

1. **Unanimity.** An item is accepted only if *every* reviewer returns `pass`.
2. **Fail closed on a missing verdict** (§4.5b). A reviewer that errors is **not** a `pass`.
   D-256 found this the expensive way: gpt-oss-120b emitted `defects[0].index = 0` against
   `Field(ge=1)` and produced no verdict at all, and "unanimous pass" is undefined when one
   reviewer says nothing. Treating an unreachable reviewer as consent would make an outage
   look like approval (CLAUDE.md rule 5).
3. **Hallucinated locations are dropped before they can reach a repair prompt**, not reported
   alongside real ones. D-254 and D-256 both measured this at zero, which is the argument for
   wiring it now rather than after the first time it is not.

**Reviewer diversity is a parameter, not a default.** The panel takes one gateway per reviewer
because the point of the second opinion is an *uncorrelated* blind spot: D-256 measured B and C
disagreeing on 9 of 50 items, and a panel of one model twice would have measured 0 and cost
double. Nothing here enforces that the gateways differ - that is a roster decision (§5.6) - but
a panel built from identical gateways is a bug that this docstring is the only warning about.
"""

import asyncio
from dataclasses import dataclass, field

from intellichoice_shared.bedrock import (
    AuthoredGeneratedItemResponse,
    BedrockGateway,
    HintSolutionDefect,
    HintSolutionReviewResponse,
)

from .hint_solution_review import out_of_range_defects, review_hints_and_solution

_BLOCKING = ("repair", "reject")


@dataclass(frozen=True)
class ReviewerReading:
    """One reviewer's contribution, including the case where it did not produce one."""

    reviewer: str
    response: HintSolutionReviewResponse | None
    error: str | None = None
    cost_cents: float = 0.0

    @property
    def blocks(self) -> bool:
        # A missing verdict blocks. See the module docstring - this is the whole of §4.5b and
        # the single most important line in the file.
        if self.response is None:
            return True
        return self.response.verdict in _BLOCKING


@dataclass(frozen=True)
class PanelVerdict:
    readings: list[ReviewerReading]
    defects: list[HintSolutionDefect] = field(default_factory=list)
    discarded_locations: list[str] = field(default_factory=list)

    @property
    def cost_cents(self) -> float:
        """What this panel cost, including reviewers that failed after being billed."""
        return sum(r.cost_cents for r in self.readings)

    @property
    def accepted(self) -> bool:
        """Unanimous `pass`. Anything else - a block, an error, an empty panel - is not."""
        return bool(self.readings) and not any(r.blocks for r in self.readings)

    @property
    def unreachable(self) -> list[str]:
        return [r.reviewer for r in self.readings if r.response is None]


def merge_defects(
    readings: list[ReviewerReading], item: AuthoredGeneratedItemResponse
) -> tuple[list[HintSolutionDefect], list[str]]:
    """Every reviewer's defects, hallucinated locations removed, order preserved.

    Returns `(usable, discarded)`. Deliberately **not** deduplicated: two reviewers naming the
    same step is the strongest signal in the panel's output, and collapsing it to one entry
    would throw away the agreement that makes it strong. A repair prompt reading the same
    location twice is a cost of a few tokens; a repair prompt that cannot tell a
    both-reviewers-agree defect from a one-reviewer defect is a worse instrument.
    """
    usable: list[HintSolutionDefect] = []
    discarded: list[str] = []
    for reading in readings:
        if reading.response is None:
            continue
        bad = set(out_of_range_defects(reading.response, item))
        discarded.extend(f"{reading.reviewer}: {problem}" for problem in sorted(bad))
        lengths = {
            "hint_ladder": len(item.hint_ladder),
            "canonical_solution": len(item.canonical_solution.steps),
        }
        usable.extend(
            defect
            for defect in reading.response.defects
            if defect.index is None or defect.index <= lengths[defect.target]
        )
    return usable, discarded


async def review_panel(
    gateways: dict[str, BedrockGateway],
    item: AuthoredGeneratedItemResponse,
    *,
    skill_name: str,
    grade_band: str,
    session_spend_cents: float,
) -> PanelVerdict:
    """Read `item` with every reviewer concurrently and collapse to one decision.

    `gateways` is `{reviewer name: gateway}` - one per reviewer, because the model is chosen by
    the gateway's registry. Reviewers run in parallel: they are independent by construction and
    serialising them would double the wall-clock of every item for no benefit.

    **`session_spend_cents` is the spend *before* this panel**, and every reviewer is told the
    same figure rather than an accumulating one. The reviewers run concurrently, so there is no
    honest sequential total to hand them; each gateway still enforces its own session budget,
    which is what actually stops a runaway. The caller is responsible for adding the panel's
    cost to its own running total.
    """
    names = list(gateways)
    results = await asyncio.gather(
        *(
            review_hints_and_solution(
                gateways[name],
                item,
                skill_name=skill_name,
                grade_band=grade_band,
                session_spend_cents=session_spend_cents,
            )
            for name in names
        ),
        return_exceptions=True,
    )

    readings: list[ReviewerReading] = []
    for name, result in zip(names, results, strict=True):
        if isinstance(result, BaseException):
            # A gateway error carries the cost of the attempt that failed - the call was
            # still billed - so it is read off the exception where the gateway provides it.
            readings.append(
                ReviewerReading(
                    reviewer=name,
                    response=None,
                    error=str(result),
                    cost_cents=float(getattr(result, "cost_cents", 0.0) or 0.0),
                )
            )
        else:
            readings.append(
                ReviewerReading(reviewer=name, response=result.value, cost_cents=result.cost_cents)
            )

    defects, discarded = merge_defects(readings, item)
    return PanelVerdict(readings=readings, defects=defects, discarded_locations=discarded)
