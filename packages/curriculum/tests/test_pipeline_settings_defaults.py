"""The curriculum pipeline's *default* model roster (DRIFT-49, D-273).

An unset environment is a real configuration, not a placeholder: `make
question-gen-authored` reads whatever `CurriculumPipelineSettings` resolves to, and until
2026-08-26 that was one id (`anthropic.claude-sonnet-5`) in all four slots - an id this
account measured `AccessDenied` (D-273 C1 Phase 0), in a shape `pipeline_cli.preflight`
refuses before the first call because Solver A and Solver B would be one opinion counted
twice.

The property these tests exist to protect is the **solver diversity of the defaults**, not
the two literal ids: availability is a dated measurement (2026-08-11) and the roster may be
re-measured. The exact ids are pinned too, because a silent drift back to a non-invocable
default is the exact defect being fixed - but if a future stratum changes them, update the
pins and keep the diversity assertions.
"""

import os

import pytest
from intellichoice_curriculum import pipeline_cli
from intellichoice_curriculum.settings import CurriculumPipelineSettings

# The 2026-08-11 stratum's invocable set (QUESTION_GENERATION.md §6, D-273).
_HAIKU = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
_SONNET_45 = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"


def _unset_env_settings(monkeypatch: pytest.MonkeyPatch) -> CurriculumPipelineSettings:
    """Settings as an environment that configures nothing would see them.

    Both isolations matter and neither substitutes for the other: `_env_file=None` stops a
    developer's real `.env` from answering for the defaults, and clearing `CURRICULUM_*`
    stops an exported shell variable from doing the same.
    """
    for name in list(os.environ):
        if name.startswith("CURRICULUM_"):
            monkeypatch.delenv(name, raising=False)
    return CurriculumPipelineSettings(_env_file=None)  # type: ignore[call-arg]


def test_default_solvers_are_two_different_models(monkeypatch: pytest.MonkeyPatch) -> None:
    """The property that must never regress, stated the way preflight states it.

    `underlying_model` rather than `!=` on purpose: `us.`/`global.` are routing aliases for
    the same weights, so a string comparison would pass on two spellings of one model.
    """
    settings = _unset_env_settings(monkeypatch)
    solver_a = pipeline_cli.underlying_model(settings.bedrock_generation_model_id)
    solver_b = pipeline_cli.underlying_model(settings.bedrock_review_model_id)
    assert solver_a != solver_b, (
        f"default Solver A and Solver B both resolve to {solver_a!r} - preflight refuses "
        f"this configuration, so an unset environment could not start a paid run"
    )


def test_default_solver_b_shares_the_generators_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """The documented asymmetric weakness, asserted so it stays deliberate.

    The invocable set is two models and three roles want independence, so one pair must
    share. D-273 puts the share on Generator/Solver B rather than on the two solvers,
    because preflight forbids the latter and the panel is what the share would hollow out.
    """
    settings = _unset_env_settings(monkeypatch)
    assert pipeline_cli.underlying_model(
        settings.bedrock_authored_generation_model_id
    ) == pipeline_cli.underlying_model(settings.bedrock_review_model_id)


def test_defaults_are_the_measured_roster(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pinned to the 2026-08-11 stratum - see this module's docstring before changing."""
    settings = _unset_env_settings(monkeypatch)
    assert settings.bedrock_authored_generation_model_id == _SONNET_45  # Generator
    assert settings.bedrock_generation_model_id == _HAIKU  # Solver A
    assert settings.bedrock_review_model_id == _SONNET_45  # Solver B
    assert settings.bedrock_judge_model_id == _HAIKU  # Judge
    # D-205: unset means "the authoring model designs the equation". Untouched by DRIFT-49.
    assert settings.bedrock_equation_design_model_id == ""
