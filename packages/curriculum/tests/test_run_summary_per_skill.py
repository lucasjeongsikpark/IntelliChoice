"""A skill that accepts nothing must be visible in the run summary (D-281).

`algebra_1` reported **33% accepted** while three of its inequality skills accepted
**nothing at all** - the gate could not express the answer their questions ask for. The
topic average hid that for a whole wave, and the number that would have shown it was never
computed. A skill at 0 is a different event from a skill at 40%: the first says the
pipeline *cannot produce this kind of question*, and re-running it only spends money again.

Free: no model call, no database.
"""

from intellichoice_curriculum.ai_pipeline import PipelineOutcome
from intellichoice_curriculum.pipeline_cli import RunSummary


def _accepted() -> PipelineOutcome:
    return PipelineOutcome(status="pending", cost_cents=1.0)


def _rejected(stage: str = "validation") -> PipelineOutcome:
    return PipelineOutcome(status="rejected", rejected_at=stage, cost_cents=1.0)  # type: ignore[arg-type]


def test_a_skill_that_accepts_nothing_is_named() -> None:
    summary = RunSummary()
    for _ in range(3):
        summary.record(_accepted(), skill_id="alg1_linear")
    for _ in range(4):
        summary.record(_rejected(), skill_id="alg1_inequalities")

    assert summary.shut_out() == ["alg1_inequalities (0 of 4)"]
    rendered = summary.format()
    assert "ACCEPTED NOTHING: alg1_inequalities (0 of 4)" in rendered
    assert "structural failure" in rendered


def test_a_skill_with_a_low_yield_is_not_named() -> None:
    """The line has to mean something. A skill that produced *one* item is not shut out,
    however bad the rate - the claim is "cannot", not "struggles"."""
    summary = RunSummary()
    summary.record(_accepted(), skill_id="alg1_quadratics")
    for _ in range(9):
        summary.record(_rejected(), skill_id="alg1_quadratics")

    assert summary.shut_out() == []
    assert "ACCEPTED NOTHING" not in summary.format()


def test_a_run_where_every_skill_produced_something_says_nothing() -> None:
    summary = RunSummary()
    summary.record(_accepted(), skill_id="a")
    summary.record(_accepted(), skill_id="b")
    assert "ACCEPTED NOTHING" not in summary.format()


def test_slots_that_never_reached_a_model_are_not_evidence_about_the_skill() -> None:
    """D-199's denominator rule, applied to the per-skill counts.

    A circuit-breaker skip says the region was unavailable, not that the skill is
    unproducible - counting it would report a shut-out skill on any run that tripped the
    breaker, which is the one moment the summary must stay trustworthy.
    """
    summary = RunSummary()
    summary.record(_rejected("circuit_open"), skill_id="alg1_inequalities")
    summary.record(_rejected("budget"), skill_id="alg1_inequalities")

    assert summary.per_skill.get("alg1_inequalities") is None
    assert summary.shut_out() == []


def test_the_worst_denominator_is_reported_first() -> None:
    """Two shut-out skills are ordered by how much evidence there is for each, so the one
    that burned twelve candidates reads before the one that burned two."""
    summary = RunSummary()
    for _ in range(2):
        summary.record(_rejected(), skill_id="small")
    for _ in range(12):
        summary.record(_rejected(), skill_id="large")

    assert summary.shut_out() == ["large (0 of 12)", "small (0 of 2)"]


def test_a_retiered_candidate_counts_as_accepted() -> None:
    """It is pending review exactly like any other item, at a different tier (D-239) - so
    a skill producing only re-tiered items is not shut out."""
    summary = RunSummary()
    summary.record(PipelineOutcome(status="retiered", cost_cents=1.0), skill_id="alg1_x")
    assert summary.shut_out() == []
