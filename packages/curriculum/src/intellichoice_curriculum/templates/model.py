"""Pydantic mirror of the SPEC §5.8.2 question_template fields (minus DB-assigned
id/created_at/version), shared by every topic's hand-authored template module.
"""

from pydantic import BaseModel

from intellichoice_curriculum.templates.registry import ParameterSchema


class QuestionTemplateDef(BaseModel):
    topic_id: str
    skill_id: str
    grade_band: str
    difficulty_label: int
    difficulty_confidence: float = 1.0
    question_type: str = "multiple_choice"
    parameter_schema: ParameterSchema
    generation_constraints: dict = {}
    solution_function: str
    correct_option_generator: str
    distractor_generators: list[str]
    common_error_tags: list[str] = []
    estimated_time_seconds: int
    generator_model: str = "hand-authored-v1"
    review_model_versions: dict = {}
