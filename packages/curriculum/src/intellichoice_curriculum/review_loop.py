"""Panel → repair → panel, up to five rounds, then discard (D-260). §4 of the design doc.

**Nothing calls this.** It is the last unbuilt piece of §4 apart from a pipeline call site, and
it stays uncalled until someone decides to run it - the position every part of this design has
been kept in since D-251.

Three things it owns that the panel and the repairer deliberately do not:

**A round limit is not a spend limit, and this enforces both.** Five rounds bounds *iterations*;
it does not bound cents, because a repair is a full authoring-shaped call whose size this module
does not control. `per_item_budget_cents` is checked before every call, so a pathological item
stops instead of spending a batch's budget inside its own round limit while looking compliant.

**Early stop on a recurring defect.** If a round's blocking defects are the same as the previous
round's, the repair is not landing and rounds 3-5 will buy the same answer again. This is the
only reason the loop keeps a history at all, and it is why a repair must be *targeted* rather
than a re-roll (§4.6): against a freshly generated item each round, "the same defect" has no
meaning and the limit degenerates into five independent generations.

**The discard keeps everything.** D-195: a pilot that rejects everything and keeps no content
leaves nothing to review. A discard here has consumed up to 17 model calls, so the record is
worth more than it was then - and it is a plain dict for `question_validation_runs.stage_results`
rather than a new table, following the `candidate_snapshot` precedent in `ai_pipeline`.
"""

from dataclasses import dataclass, field

from intellichoice_shared.bedrock import (
    AuthoredGeneratedItemResponse,
    BedrockGateway,
    HintSolutionDefect,
)

from .hint_solution_repair import (
    apply_repair,
    collateral_edits,
    repair_hints_and_solution,
)
from .review_panel import PanelVerdict, review_panel

#: §4's limit. A constant rather than a default argument so the number has one home.
MAX_REPAIR_ROUNDS = 5


@dataclass
class Round:
    """One panel reading and the repair it provoked, if any."""

    number: int
    accepted: bool
    verdicts: dict[str, str | None]
    defects: list[str]
    discarded_locations: list[str] = field(default_factory=list)
    unreachable: list[str] = field(default_factory=list)
    # `suggested_fix` beside what actually replaced it, so verbatim adoption of a reviewer's
    # wording is countable rather than argued about - see `hint_solution_repair`'s docstring
    # on why that is the risk this channel creates.
    suggested_fixes: list[str] = field(default_factory=list)
    repaired_hint_ladder: list[str] | None = None
    repair_error: str | None = None
    # D-261: positions the repair changed that no defect named. A rejected repair is not a
    # rejected item - the round is discarded and the item keeps the text it came in with.
    collateral_edits: list[str] = field(default_factory=list)


@dataclass
class LoopOutcome:
    status: str  # "accepted" | "discarded"
    item: AuthoredGeneratedItemResponse
    rounds: list[Round]
    spend_cents: float
    stopped_because: str

    def as_evidence(self) -> dict:
        """A plain dict for `stage_results`, readable without this module (D-195)."""
        return {
            "status": self.status,
            "stopped_because": self.stopped_because,
            "spend_cents": self.spend_cents,
            "rounds": [
                {
                    "number": r.number,
                    "accepted": r.accepted,
                    "verdicts": r.verdicts,
                    "defects": r.defects,
                    "discarded_locations": r.discarded_locations,
                    "unreachable": r.unreachable,
                    "suggested_fixes": r.suggested_fixes,
                    "repaired_hint_ladder": r.repaired_hint_ladder,
                    "repair_error": r.repair_error,
                    "collateral_edits": r.collateral_edits,
                }
                for r in self.rounds
            ],
        }


def _fingerprint(defects: list[HintSolutionDefect]) -> list[str]:
    """What "the same defect again" means: location plus problem, ignoring the suggestion.

    Two reviewers wording the same objection differently would defeat exact-string matching,
    and that is accepted: the early stop is an optimisation, and a *missed* stop costs one
    extra round while a *false* stop discards a recoverable item. The asymmetry decides the
    design.
    """
    return sorted(f"{d.target}[{d.index}]:{d.problem}" for d in defects)


def _round_record(number: int, verdict: PanelVerdict) -> Round:
    return Round(
        number=number,
        accepted=verdict.accepted,
        verdicts={
            r.reviewer: (r.response.verdict if r.response else None) for r in verdict.readings
        },
        defects=[f"{d.target}[{d.index}]: {d.problem}" for d in verdict.defects],
        discarded_locations=list(verdict.discarded_locations),
        unreachable=list(verdict.unreachable),
        suggested_fixes=[d.suggested_fix for d in verdict.defects],
    )


async def run_review_loop(
    *,
    reviewers: dict[str, BedrockGateway],
    repairer: BedrockGateway,
    item: AuthoredGeneratedItemResponse,
    skill_name: str,
    grade_band: str,
    per_item_budget_cents: float,
    max_rounds: int = MAX_REPAIR_ROUNDS,
    session_spend_cents: float = 0.0,
) -> LoopOutcome:
    """Read, repair, re-read, until unanimity or a limit. Never raises for a model failure.

    Returns `status="accepted"` only on a unanimous `pass` from a full panel. Everything else
    - blocked at the round limit, out of budget, a reviewer that never answered, a repairer
    that failed - is `"discarded"`, because §4.5 has no human escalation path and an item that
    cannot be shown to be sound is not shown to a student.
    """
    rounds: list[Round] = []
    spend = 0.0
    current = item
    previous_fingerprint: list[str] | None = None

    for number in range(1, max_rounds + 2):  # one initial reading, then up to `max_rounds`
        if spend >= per_item_budget_cents:
            return LoopOutcome("discarded", current, rounds, spend, "per-item budget reached")

        verdict = await review_panel(
            reviewers,
            current,
            skill_name=skill_name,
            grade_band=grade_band,
            session_spend_cents=session_spend_cents + spend,
        )
        spend += verdict.cost_cents
        record = _round_record(number, verdict)
        rounds.append(record)

        if verdict.accepted:
            return LoopOutcome("accepted", current, rounds, spend, "unanimous pass")

        if number > max_rounds:
            return LoopOutcome("discarded", current, rounds, spend, "repair limit reached")

        fingerprint = _fingerprint(verdict.defects)
        if fingerprint and fingerprint == previous_fingerprint:
            return LoopOutcome("discarded", current, rounds, spend, "same defects recurred")
        previous_fingerprint = fingerprint

        if not verdict.defects:
            # A block with nothing located: the response model forbids it, so this means every
            # located defect was filtered as hallucinated, or the only blocker was a reviewer
            # that never answered. Repairing against nothing would be a re-roll wearing a
            # loop's clothing (§4.6), so stop.
            return LoopOutcome("discarded", current, rounds, spend, "blocked with no usable defect")

        if spend >= per_item_budget_cents:
            return LoopOutcome("discarded", current, rounds, spend, "per-item budget reached")

        try:
            repair = await repair_hints_and_solution(
                repairer,
                current,
                verdict.defects,
                skill_name=skill_name,
                grade_band=grade_band,
                session_spend_cents=session_spend_cents + spend,
            )
        except Exception as exc:
            # Deliberately broad: a repairer failing for any reason must discard the item
            # rather than abort a batch - the same choice `review_panel` makes for a reviewer
            # that raises. A `BedrockGatewayError` still carries the cost of the failed
            # attempt, and the caller paid for it either way.
            spend += float(getattr(exc, "cost_cents", 0.0) or 0.0)
            record.repair_error = str(exc)
            return LoopOutcome("discarded", current, rounds, spend, "repair failed")

        spend += repair.cost_cents
        collateral = collateral_edits(current, repair.value, verdict.defects)
        if collateral:
            # D-261: the repair edited text nobody objected to. Applying it would leave the
            # panel reviewing changes it never asked for, and `mistral-large-3` did exactly
            # this on 4 of 4 measured attempts - so this is an enforced invariant rather than
            # a prompt clause anyone has to trust. The item keeps what it came in with.
            record.collateral_edits = collateral
            return LoopOutcome("discarded", current, rounds, spend, "repair edited unnamed text")
        record.repaired_hint_ladder = list(repair.value.hint_ladder)
        current = apply_repair(current, repair.value)

    # Unreachable: the loop returns from inside. Present so a future edit to the range cannot
    # fall out of the function with no outcome.
    return LoopOutcome("discarded", current, rounds, spend, "loop exhausted")
