"""SPEC §5.31.1-§5.31.4 evaluation-category registry (S30, plan §13).

Every evaluator/golden-dataset category SPEC names already lives - correctly - next to
the code it tests (S3-S28 built these as ordinary pytest suites, not a separate "eval"
concern). This module doesn't reimplement any of it; it's the one indexed place that
maps each named SPEC item to where its coverage actually lives, so "is X evaluated"
has one place to check instead of a spec-to-codebase memory exercise. `test_ref`
entries are repo-relative test *file* paths (not function names) - coverage is
asserted at file-existence granularity deliberately: pinning exact function names would
make this registry break every time a test is sensibly renamed without any real loss of
coverage, which is exactly the kind of premature rigidity worth avoiding here.

A `not_applicable_reason` (not a missing `test_refs`) marks a SPEC item this codebase
has no feature for yet, by an already-recorded decision - never a silent gap.
"""

from dataclasses import dataclass
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[4]


@dataclass(frozen=True)
class EvalItem:
    name: str
    test_refs: tuple[str, ...] = ()
    not_applicable_reason: str | None = None

    def __post_init__(self) -> None:
        if not self.test_refs and not self.not_applicable_reason:
            raise ValueError(f"{self.name!r} needs test_refs or a not_applicable_reason")


@dataclass(frozen=True)
class EvalCategory:
    name: str
    spec_ref: str
    items: tuple[EvalItem, ...]


DETERMINISTIC_EVALUATORS = EvalCategory(
    name="Deterministic Evaluators",
    spec_ref="§5.31.1",
    items=(
        EvalItem("Attendance gating", ("apps/learning-api/tests/test_auth_and_attendance.py",)),
        EvalItem(
            "Parent-child authorization", ("apps/learning-api/tests/test_auth_and_attendance.py",)
        ),
        EvalItem(
            "Number of questions per difficulty", ("packages/curriculum/tests/test_loader.py",)
        ),
        EvalItem("Multiple-choice grading", ("apps/learning-api/tests/test_exam_backend.py",)),
        EvalItem("Score calculation", ("apps/learning-api/tests/test_exam_backend.py",)),
        EvalItem(
            "Learning-gain calculation",
            (
                "apps/learning-api/tests/test_mastery_bootstrap.py",
                "apps/learning-api/tests/test_exam_flow_determinism.py",
            ),
        ),
        EvalItem("Graph routing", ("apps/learning-api/tests/test_learning_graph_routes.py",)),
        EvalItem("Email approval", ("apps/chat-api/tests/test_admin_escalation.py",)),
        EvalItem("Calendar approval", ("apps/chat-api/tests/test_calendar_action.py",)),
        EvalItem(
            "Citation presence",
            ("apps/chat-api/tests/test_qa_graph.py", "apps/chat-api/tests/test_qa_service.py"),
        ),
        EvalItem("Role metadata filtering", ("apps/chat-api/tests/test_role_access.py",)),
        EvalItem("Quarantine threshold", ("apps/learning-api/tests/test_question_reports.py",)),
        EvalItem(
            "Image deletion event",
            not_applicable_reason=(
                "S29 (multimodal solution images, SPEC §5.17) was deferred, not built - "
                "see D-078. No image-upload feature exists to emit this event."
            ),
        ),
    ),
)

EXECUTABLE_EVALUATORS = EvalCategory(
    name="Executable Evaluators",
    spec_ref="§5.31.2",
    items=(
        EvalItem(
            "Mathematical answer",
            ("packages/curriculum/tests/test_authored_validation.py",),
        ),
        EvalItem(
            "Distractor uniqueness",
            ("packages/curriculum/tests/test_authored_validation.py",),
        ),
        EvalItem(
            "Equation solution", ("packages/curriculum/tests/test_authored_validation.py",)
        ),
        EvalItem(
            "Parameter constraints",
            not_applicable_reason=(
                "D-226 removed the parameterized shape templates, which were the only "
                "content with numeric parameters to constrain. An authored item is a fixed "
                "piece of text with one canonical variant - there is no parameter schema "
                "to satisfy at serving time, and the constraints that remain are on the "
                "item's own fields, covered by 'Mathematical answer' above."
            ),
        ),
        EvalItem(".ics syntax", ("packages/adapters/tests/test_ics.py",)),
        EvalItem(
            "SQL parser validation",
            not_applicable_reason=(
                "This codebase has no free-text-to-SQL feature (CLAUDE.md non-negotiable "
                "#2, 'No runtime NL2SQL') - there is no generated SQL to parse or validate."
            ),
        ),
        EvalItem(
            "Pydantic schema",
            (
                "packages/shared/tests/test_generation_payload_schemas.py",
                "packages/shared/tests/test_bedrock_payload_pii_floor.py",
            ),
        ),
        EvalItem(
            "API contract",
            (
                "apps/learning-api/tests/test_exam_backend.py",
                "apps/learning-api/tests/test_dashboard_report_endpoints.py",
            ),
            # Illustrative, not exhaustive - every FastAPI route's `response_model`
            # already enforces its own contract on every HTTP-level test in both apps'
            # test suites; there is no separate OpenAPI-snapshot test in this codebase.
        ),
        EvalItem(
            "Question variant generation",
            ("apps/learning-api/tests/test_authored_serving.py",),
            # D-226: a served variant is now a copy of the item's canonical variant rather
            # than a rendering from a seed, so the evidence moved with the mechanism.
        ),
    ),
)

GOLDEN_DATASET_LEARNING = EvalCategory(
    name="Golden Dataset - Learning",
    spec_ref="§5.31.4",
    items=(
        EvalItem("Grade-to-topic mapping", ("packages/curriculum/tests/test_content.py",)),
        EvalItem(
            "Difficulty-specific questions", ("packages/curriculum/tests/test_loader.py",)
        ),
        # D-226: both used to point at the shape bank's tests (`test_templates.py`,
        # `test_hint_ladders.py`), which covered content `_servable()` had filtered out of
        # every serving read since D-210 - so this category was evidencing questions and
        # hints no student could be shown. Re-pointed at the authored bank, which is what
        # is actually served: its per-item `common_error_tags` and `hint_ladder` are gated
        # by `validate_authored_item` on every load in every environment.
        EvalItem("Common errors", ("packages/curriculum/tests/test_authored_bank.py",)),
        EvalItem(
            "Hints",
            (
                "packages/curriculum/tests/test_authored_validation.py",
                "packages/curriculum/tests/test_mock_hint_is_leak_clean.py",
                "packages/evals/tests/test_leak_sample.py",
            ),
        ),
        EvalItem("Solutions", ("apps/learning-api/tests/test_tutor_service.py",)),
        EvalItem("Video routing", ("apps/learning-api/tests/test_video_catalog.py",)),
        EvalItem("Attendance branches", ("apps/learning-api/tests/test_auth_and_attendance.py",)),
        EvalItem(
            "Parent-child authorization", ("apps/learning-api/tests/test_auth_and_attendance.py",)
        ),
        EvalItem(
            "Pre/post parallel forms",
            ("apps/learning-api/tests/test_learning_flow.py",),
        ),
        EvalItem("Memory consolidation", ("packages/memory/tests/test_consolidation.py",)),
    ),
)

GOLDEN_DATASET_QA = EvalCategory(
    name="Golden Dataset - Q&A",
    spec_ref="§5.31.4",
    items=(
        EvalItem(
            "Public FAQ",
            (
                "apps/chat-api/tests/fixtures/qa_coverage_eval.yaml",
                "apps/chat-api/tests/test_qa_coverage_eval.py",
            ),
        ),
        EvalItem(
            "Role-specific FAQ",
            (
                "apps/chat-api/tests/fixtures/qa_coverage_eval.yaml",
                "apps/chat-api/tests/test_role_access.py",
            ),
        ),
        EvalItem("Branch questions", ("apps/chat-api/tests/test_branch_locator.py",)),
        EvalItem("Academic calendar", ("apps/chat-api/tests/test_calendar_events.py",)),
        EvalItem("Conflicting sources", ("apps/chat-api/tests/test_qa_service.py",)),
        EvalItem(
            "No-answer cases",
            (
                "apps/chat-api/tests/fixtures/qa_coverage_eval.yaml",
                # S37/AUD-C: the paid run is what actually measures this. Under the
                # default mock the `no_answer` category scores 0/8 by construction
                # (`_rag_answer_json` always answers from the first chunk), so the
                # mock-backed file above records the case set, not the capability.
                "apps/chat-api/tests/test_qa_coverage_eval_real_bedrock.py",
            ),
        ),
        EvalItem("Maps tool", ("apps/chat-api/tests/test_branch_locator.py",)),
        EvalItem("Calendar tool", ("apps/chat-api/tests/test_calendar_action.py",)),
        EvalItem("Gmail escalation", ("apps/chat-api/tests/test_admin_escalation.py",)),
        EvalItem("Out-of-scope requests", ("apps/chat-api/tests/fixtures/qa_coverage_eval.yaml",)),
        EvalItem(
            "Prompt injection",
            (
                "apps/chat-api/tests/test_prompt_injection_eval.py",
                # S37/AUD-C added an `adversarial` category to the coverage fixture so
                # the same pressure is tracked as a *rate* comparable across runs and
                # across providers, not only as per-case invariants.
                "apps/chat-api/tests/fixtures/qa_coverage_eval.yaml",
            ),
        ),
        EvalItem(
            "Paraphrase robustness",
            (
                "apps/chat-api/tests/fixtures/qa_coverage_eval.yaml",
                "apps/chat-api/tests/test_qa_coverage_eval_real_bedrock.py",
            ),
        ),
    ),
)

GOLDEN_DATASET_BAD_ITEMS = EvalCategory(
    name="Golden Dataset - Authored Question Bank Bad Items",
    spec_ref="§5.8.5 / ROADMAP S20",
    items=(
        EvalItem(
            "Two correct options",
            ("packages/curriculum/tests/test_authored_pipeline.py",),
        ),
        EvalItem(
            "Leaked answer in a hint",
            ("packages/curriculum/tests/test_authored_pipeline.py",),
        ),
        EvalItem(
            "Solution disagreeing with answer",
            ("packages/curriculum/tests/test_authored_pipeline.py",),
        ),
        EvalItem(
            "Off-grade vocabulary", ("packages/curriculum/tests/test_authored_pipeline.py",)
        ),
        EvalItem(
            "Near-duplicate pair", ("packages/curriculum/tests/test_authored_pipeline.py",)
        ),
    ),
)

ALL_CATEGORIES = (
    DETERMINISTIC_EVALUATORS,
    EXECUTABLE_EVALUATORS,
    GOLDEN_DATASET_LEARNING,
    GOLDEN_DATASET_QA,
    GOLDEN_DATASET_BAD_ITEMS,
)


def missing_test_refs() -> list[str]:
    """Every `(category, item, test_ref)` whose referenced file doesn't exist - empty
    means the registry's own claims about where coverage lives are all still true.
    """
    missing = []
    for category in ALL_CATEGORIES:
        for item in category.items:
            for ref in item.test_refs:
                if not (_REPO_ROOT / ref).exists():
                    missing.append(f"{category.name} / {item.name} / {ref}")
    return missing
