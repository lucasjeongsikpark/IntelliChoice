"""The E5.3 invocability probe classifies a Bedrock error the way preflight does.

D-273's lesson is that `agreementAvailability = AVAILABLE` is not a promise you can call
the model, so a paid run's evidence needs a per-model, dated, account-scoped verdict. The
classification has to match `pipeline_cli._unavailable_models` exactly: only *access*
errors mean "not invocable". A throttle says nothing about configuration, and failing a run
on one would be worse than the problem the check solves.

Pure: no AWS call, no network.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys

from intellichoice_curriculum.settings import CurriculumPipelineSettings

ROOT = pathlib.Path(__file__).resolve().parents[3]
HARNESS = (
    ROOT
    / "benchmarks"
    / "resume_evidence"
    / "05_content_generation"
    / "model_invocability_probe.py"
)


def _load_harness():
    spec = importlib.util.spec_from_file_location("e5_3_model_invocability_probe", HARNESS)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


probe = _load_harness()


def test_no_error_is_invocable() -> None:
    assert probe.classify(None) == "invocable"


def test_only_access_errors_are_not_invocable() -> None:
    for code in ("AccessDeniedException", "ValidationException", "ResourceNotFoundException"):
        assert probe.classify(code) == "not_invocable", code


def test_a_throttle_is_inconclusive_never_a_failure() -> None:
    assert probe.classify("ThrottlingException") == "inconclusive"
    assert probe.classify("ServiceUnavailableException") == "inconclusive"


def test_the_blocking_codes_match_the_preflights_own_list() -> None:
    """A second copy of this list is only safe while it is the same list."""
    source = (
        ROOT / "packages" / "curriculum" / "src" / "intellichoice_curriculum" / "pipeline_cli.py"
    ).read_text(encoding="utf-8")
    for code in probe.BLOCKING_ERROR_CODES:
        assert f'"{code}"' in source, code


def test_the_roster_covers_every_slot_the_run_will_call() -> None:
    slots = probe.roster(CurriculumPipelineSettings())
    assert set(slots) == {
        "generator (authored)",
        "solver_a",
        "solver_b",
        "judge",
        "equation_design",
    }
    assert all(value for value in slots.values()), slots


def test_equation_design_falls_back_to_the_authoring_model() -> None:
    """`_build_gateway` resolves it that way, so a probe that skipped the fallback would
    report on a model the run never calls."""
    settings = CurriculumPipelineSettings(bedrock_equation_design_model_id="")
    slots = probe.roster(settings)
    assert slots["equation_design"] == settings.bedrock_authored_generation_model_id
