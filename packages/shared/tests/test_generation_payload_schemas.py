"""The S9 question-generation payloads carry curriculum content, not student PII, so
they aren't bound by the §5.30.1 field-allowlist the tutor payload is. But each must
still be a strict `extra="forbid"` model - that's the "no ad-hoc dict payloads cross the
gateway" invariant `bedrock.py`'s module docstring claims when it generalizes
`generate_structured`'s `payload` type to `BaseModel` (D-023).
"""

import pytest
from intellichoice_shared.bedrock import (
    AlignmentReviewPayload,
    AmbiguityReviewPayload,
    AuthoredGeneratorPayload,
    DifficultyReviewPayload,
    GeneratorPayload,
    QuestionJudgePayload,
    SolverPayload,
)
from pydantic import BaseModel, ValidationError

_GENERATION_PAYLOADS = [
    GeneratorPayload,
    SolverPayload,
    DifficultyReviewPayload,
    AmbiguityReviewPayload,
    AlignmentReviewPayload,
    AuthoredGeneratorPayload,
    QuestionJudgePayload,
]


@pytest.mark.parametrize("payload_cls", _GENERATION_PAYLOADS)
def test_generation_payloads_forbid_extra_fields(payload_cls: type[BaseModel]) -> None:
    assert payload_cls.model_config.get("extra") == "forbid"


def test_generator_payload_rejects_unknown_extra_field() -> None:
    with pytest.raises(ValidationError):
        GeneratorPayload(
            topic_name="Linear Equations",
            skill_name="One-Step Equations",
            grade_band="6-7",
            difficulty_label=1,
            allowed_shape_keys=["one_step_add"],
            allowed_correct_option_generators=["format_integer"],
            allowed_distractor_generator_keys=["distractor_off_by_one"],
            student_external_id="student-ext-1",  # type: ignore[call-arg]
        )


def test_solver_payload_only_carries_question_and_options() -> None:
    # The solver must never be told which option is correct (SPEC §5.8.4 "independent
    # solver agreement") - the field set is exactly the stem + four options.
    assert set(SolverPayload.model_fields) == {
        "rendered_question",
        "option_a",
        "option_b",
        "option_c",
        "option_d",
    }
