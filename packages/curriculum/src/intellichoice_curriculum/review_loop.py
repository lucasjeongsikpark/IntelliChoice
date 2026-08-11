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

from collections.abc import Callable
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
    contributed_unresolved: bool = False


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
                    "contributed_unresolved": r.contributed_unresolved,
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


def _round_record(
    number: int, verdict: PanelVerdict, defects: list[HintSolutionDefect]
) -> Round:
    """`defects` is what actually drove the repair, panel plus any contributor - not
    `verdict.defects`. D-195's rule is that the record explains the outcome, and a round
    whose repair was opened by a contributed defect (D-263) would otherwise read as a repair
    with no cause.
    """
    return Round(
        number=number,
        accepted=verdict.accepted,
        verdicts={
            r.reviewer: (r.response.verdict if r.response else None) for r in verdict.readings
        },
        defects=[f"{d.target}[{d.index}]: {d.problem}" for d in defects],
        discarded_locations=list(verdict.discarded_locations),
        unreachable=list(verdict.unreachable),
        suggested_fixes=[d.suggested_fix for d in defects],
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
    first_round_defects: list[HintSolutionDefect] | None = None,
    contributed_resolved: Callable[[AuthoredGeneratedItemResponse], bool] | None = None,
) -> LoopOutcome:
    """Read, repair, re-read, until unanimity or a limit. Never raises for a model failure.

    Returns `status="accepted"` only on a unanimous `pass` from a full panel. Everything else
    - blocked at the round limit, out of budget, a reviewer that never answered, a repairer
    that failed - is `"discarded"`, because §4.5 has no human escalation path and an item that
    cannot be shown to be sound is not shown to a student.

    ### `first_round_defects`, and why it is first-round only (D-263)

    D-262 measured the panel passing **5 of 10** items selected for carrying a defect a free
    deterministic check finds every time. The obvious fix - tell the reviewers what the check
    found - is **circular**: recall rises trivially when the answer is handed over, and both
    reviewers hearing the same hint collapses the independence D-256 measured. The reviewers
    are therefore never told.

    Instead a caller may contribute located defects that **open the repair path on round 1**.
    Two properties follow, and both are the point:

    - **It can never reject an item.** From round 2 the panel alone decides, so a heuristic
      contributor cannot hold an item blocked. D-257 was explicit that its audit is not an
      exact invariant and must not become a gate; this is how it contributes without becoming
      one. A false positive costs one repair round, not an item.
    - **Acceptance stays the panel's verdict.** The contributed defect buys an attempt, never
      an approval.

    `contributed_resolved` closes the hole D-264 measured (D-266). A contributed defect opens a
    repair that **nothing verifies** - the panel cannot check it, because the panel never saw it,
    which is the entire reason it had to be contributed. Two of 44 items reached acceptance with
    the contributed defect untouched. When the callback is supplied and returns `False` after a
    repair, **the repair is rejected and the item keeps the text it came in with** - the same
    shape as `collateral_edits`, and the reason it does not violate D-257's "the audit is not a
    gate":

    **the audit still cannot reject an item; it can only decline to repair one.** For bank
    repair those are the same outcome as doing nothing, so a false positive costs nothing at
    all. That asymmetry does *not* hold in the generation pipeline, where a discard throws away
    a candidate that was paid for - so a generation caller should think before passing this.
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
        defects = list(verdict.defects)
        if number == 1 and first_round_defects:
            # Contributed, not authoritative. Appended so the panel's own findings come first
            # in the repair prompt - the reviewers read the item, the contributor read one
            # property of it.
            defects.extend(first_round_defects)
        record = _round_record(number, verdict, defects)
        rounds.append(record)

        if verdict.accepted and not (number == 1 and first_round_defects):
            return LoopOutcome("accepted", current, rounds, spend, "unanimous pass")

        if number > max_rounds:
            return LoopOutcome("discarded", current, rounds, spend, "repair limit reached")

        fingerprint = _fingerprint(defects)
        if fingerprint and fingerprint == previous_fingerprint:
            return LoopOutcome("discarded", current, rounds, spend, "same defects recurred")
        previous_fingerprint = fingerprint

        if not defects:
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
                defects,
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
        collateral = collateral_edits(current, repair.value, defects)
        if collateral:
            # D-261: the repair edited text nobody objected to. Applying it would leave the
            # panel reviewing changes it never asked for, and `mistral-large-3` did exactly
            # this on 4 of 4 measured attempts - so this is an enforced invariant rather than
            # a prompt clause anyone has to trust. The item keeps what it came in with.
            record.collateral_edits = collateral
            return LoopOutcome("discarded", current, rounds, spend, "repair edited unnamed text")
        repaired = apply_repair(current, repair.value)
        if number == 1 and first_round_defects and contributed_resolved is not None:
            if not contributed_resolved(repaired):
                record.contributed_unresolved = True
                return LoopOutcome(
                    "discarded", current, rounds, spend, "contributed defect not resolved"
                )
        record.repaired_hint_ladder = list(repair.value.hint_ladder)
        current = repaired

    # Unreachable: the loop returns from inside. Present so a future edit to the range cannot
    # fall out of the function with no outcome.
    return LoopOutcome("discarded", current, rounds, spend, "loop exhausted")
