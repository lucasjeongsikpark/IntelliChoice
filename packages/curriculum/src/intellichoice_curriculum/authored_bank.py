"""Approved authored items as versioned files, so reviewed content reaches every environment.

D-190. Until now authored content existed only as rows in whatever database the S20
pipeline was pointed at, and approval was a row update - so a reviewed item could not
reach CI, staging or production at all. D-189 proved that concretely: five items were
approved locally, the suite went green, and CI failed because its database is seeded from
`loader.py` and had none of them.

The shape bank solves the same problem by living in `templates/linear_equations.py` and
being loaded into every environment. Authored content cannot use that shape exactly - a
shape template is a *generator* whose one rendering the loader recomputes deterministically
from a seed, while an authored item *is* its content - so the item is stored in full,
under `curriculum/internal_math/authored/`, which both Dockerfiles already `COPY`.

Two properties this is designed for, beyond "the content exists somewhere":

- **Content changes become reviewable pull requests.** The file is the artifact a human
  approved (D-026), so what shipped and who approved it is in git history rather than in
  one database's `validation_status` column.
- **The file is re-validated on load, not trusted.** It is plain YAML that anyone can
  hand-edit, and it is loaded into every environment including production, so `loader.py`
  runs the same §5.8.5 deterministic gate the pipeline ran (`validate_authored_item`) and
  aborts the whole run on failure. Editing a correct answer in the file without editing
  its options fails the load rather than reaching a student.

**`stem_embedding` is deliberately not exported.** It is 1024 floats per item, which would
make a reviewable file unreviewable, and nothing on the serving path reads it - its only
use is `stem_near_duplicate_exists` during authoring. The cost is real and scoped: an
authoring run in an environment seeded from these files can only text-dedup against them
until they are re-embedded (the same relationship `make knowledge-reembed` has with the RAG
corpus). Exact-text dedup still applies, and it is what caught five of D-188's seven
rejections.
"""

from pathlib import Path

import yaml
from intellichoice_shared.bedrock import (
    AuthoredGeneratedItemResponse,
    SolutionResponse,
)
from pydantic import BaseModel, ConfigDict

from intellichoice_curriculum.content import DEFAULT_CONTENT_ROOT

DEFAULT_AUTHORED_ROOT = DEFAULT_CONTENT_ROOT / "authored"

# Every authored template carries these, and they are the same for all of them: the
# columns exist for shape templates and are what `renders_from_canonical_variant` keys on.
# Stored once here rather than repeated on every item in the file, where they would be
# noise a reviewer has to skip past on the way to the actual question.
AUTHORED_SOLUTION_FUNCTION = "authored"
AUTHORED_MODE = "authored"


class AuthoredTemplateDef(BaseModel):
    """One approved authored item: the template's content plus its canonical variant.

    `extra="forbid"` so a typo in a hand-edited file is a load error rather than a field
    that silently does nothing - the same reasoning as every Bedrock payload model (D-023).
    """

    model_config = ConfigDict(extra="forbid")

    question_template_id: str
    topic_id: str
    skill_id: str
    grade_band: str
    difficulty_label: int
    difficulty_confidence: float = 1.0
    estimated_time_seconds: int
    common_error_tags: list[str] = []

    # Provenance of the item, carried so the file records how it was produced and what
    # judged it - the review trail is the point of putting content in git.
    generator_model: str
    review_model_versions: dict[str, str] = {}
    review_priority: str = "normal"
    version: int = 1

    # The item itself.
    stem: str
    context_block: str | None = None
    answer_expression: str | None = None
    hint_ladder: list[str]
    canonical_solution: dict

    # The canonical variant. `rendered_question` is derived from stem/context_block by the
    # pipeline but stored rather than recomputed, so the file says exactly what a student
    # sees instead of implying it.
    random_seed: int
    rendered_question: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    correct_option: str

    def to_generated_item(self) -> AuthoredGeneratedItemResponse:
        """Rebuild the pipeline's own response shape, so the loader can re-run the exact
        §5.8.5 validation suite the item passed when it was generated.

        The two difficulty fields (D-194) are reconstructed rather than restored, and this
        is the honest version of that: `proposed_difficulty` is the tier the item is
        *stored* at, which is true but is not necessarily what the generator proposed, and
        the rationale says so in words rather than inventing one. Neither field is read by
        `validate_authored_item` - the §5.8.5 gate checks options, hints, wording and the
        equation - so nothing downstream is deceived by the placeholder. The generator's
        real proposal and rationale live in `question_validation_runs`, which is authoring
        evidence and deliberately not shipped in the served bank.
        """
        return AuthoredGeneratedItemResponse(
            proposed_difficulty=self.difficulty_label,
            difficulty_rationale=(
                "Reconstructed from the versioned bank; the generator's original rationale "
                "is in this item's validation run, not in the served content."
            ),
            stem=self.stem,
            context_block=self.context_block,
            option_a=self.option_a,
            option_b=self.option_b,
            option_c=self.option_c,
            option_d=self.option_d,
            correct_option=self.correct_option,  # type: ignore[arg-type]
            equation=self.answer_expression,
            hint_ladder=self.hint_ladder,
            canonical_solution=SolutionResponse.model_validate(self.canonical_solution),
            misconception_tags=self.common_error_tags,
            estimated_time_seconds=self.estimated_time_seconds,
        )


class AuthoredBankFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    curriculum_version: str
    topic_id: str
    templates: list[AuthoredTemplateDef]


def load_authored_bank(root: Path | None = None) -> dict[str, list[AuthoredTemplateDef]]:
    """topic_id -> approved authored items, read from `<root>/<topic_id>.yaml`.

    A missing directory is empty rather than an error: an environment is allowed to have
    no authored content, and that is the state every environment was in before D-190.
    """
    directory = root or DEFAULT_AUTHORED_ROOT
    if not directory.is_dir():
        return {}
    banks: dict[str, list[AuthoredTemplateDef]] = {}
    for path in sorted(directory.glob("*.yaml")):
        parsed = AuthoredBankFile.model_validate(yaml.safe_load(path.read_text()))
        if parsed.topic_id != path.stem:
            raise ValueError(
                f"{path} declares topic_id={parsed.topic_id!r} but is named for "
                f"{path.stem!r} - the filename is what the loader groups by"
            )
        banks.setdefault(parsed.topic_id, []).extend(parsed.templates)
    return banks
