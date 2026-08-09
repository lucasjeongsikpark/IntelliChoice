"""D-190: approved authored content as a versioned file the loader reads.

The gap these cover was found by CI, not by reasoning: D-189 approved five authored items
locally, the suite went green, and CI failed because its database is seeded from
`loader.py` and had none of them. Approval was a row update in one database, so no
reviewed item could reach CI, staging or production.

Real Postgres via a rollback session (D-013), same pattern as `test_loader.py`.
"""

import asyncio
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
import yaml
from intellichoice_curriculum.authored_bank import (
    AuthoredBankFile,
    AuthoredTemplateDef,
    load_authored_bank,
)
from intellichoice_curriculum.authored_validation import validate_authored_item
from intellichoice_curriculum.content import load_curriculum
from intellichoice_curriculum.export_cli import build_bank_file, render_bank_file
from intellichoice_curriculum.loader import (
    CurriculumLoadError,
    LoadSummary,
    _load_authored_templates,
)
from intellichoice_db.engine import create_engine
from intellichoice_db.repositories.questions import QuestionRepository
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def _postgres_skip_reason() -> str | None:
    async def check() -> str | None:
        engine = create_engine()
        try:
            async with engine.connect() as conn:
                try:
                    await conn.execute(text("SELECT 1 FROM topics LIMIT 1"))
                except Exception:
                    return "Postgres schema is not migrated (run `make up && make db-upgrade`)"
            return None
        except Exception:
            return "PostgreSQL is not reachable at localhost:5432 (run `make up`)"
        finally:
            await engine.dispose()

    return asyncio.run(check())


pytestmark = pytest.mark.skipif(
    (_reason := _postgres_skip_reason()) is not None, reason=_reason or ""
)


@asynccontextmanager
async def _rollback_session() -> AsyncIterator[AsyncSession]:
    engine = create_engine()
    try:
        async with engine.connect() as conn:
            trans = await conn.begin()
            session = AsyncSession(bind=conn, join_transaction_mode="create_savepoint")
            try:
                yield session
            finally:
                await session.close()
                await trans.rollback()
    finally:
        await engine.dispose()


def _item(**overrides: object) -> AuthoredTemplateDef:
    base: dict[str, object] = dict(
        question_template_id="authored-bank-test-item",
        topic_id="linear_equations",
        skill_id="linear_one_step",
        grade_band="6-7",
        difficulty_label=1,
        estimated_time_seconds=45,
        generator_model="test",
        stem="Solve for x: x + 3 = 7",
        hint_ladder=["What undoes adding 3?", "Subtract 3 from both sides.", "Compute 7 - 3."],
        canonical_solution={
            "steps": [
                {"step_number": 1, "explanation": "Subtract 3.", "expression": "x = 7 - 3"}
            ],
            "final_answer": "4",
        },
        answer_expression="Eq(x + 3, 7)",
        random_seed=1,
        rendered_question="Solve for x: x + 3 = 7",
        option_a="4",
        option_b="5",
        option_c="10",
        option_d="3",
        correct_option="a",
    )
    base.update(overrides)
    return AuthoredTemplateDef(**base)  # type: ignore[arg-type]


def test_the_repo_bank_file_parses_and_every_item_still_validates() -> None:
    """The file is hand-editable YAML that loads into production, so it is guarded here.

    This is the cheap half of the load-time gate: it runs with no database and fails on a
    typo, a broken schema, or an edit that leaves an item's options disagreeing with its
    answer - without waiting for someone to run the loader.
    """
    banks = load_authored_bank()
    for topic_id, templates in banks.items():
        assert templates, f"{topic_id}.yaml exists but declares no templates"
        ids = [t.question_template_id for t in templates]
        assert len(set(ids)) == len(ids), f"duplicate template ids in {topic_id}.yaml"
        for template in templates:
            result = validate_authored_item(
                template.difficulty_label, template.to_generated_item()
            )
            assert result.passed, f"{template.question_template_id}: {result.failures}"


def test_the_repo_bank_file_matches_what_the_database_would_export() -> None:
    """Catches the drift that D-189 shipped: approved locally, never exported.

    An item approved in a database but absent from the file reaches no other environment,
    which is the exact failure this whole mechanism exists to prevent - so it fails here,
    in the repository, rather than silently on someone else's machine.
    """

    async def run() -> None:
        curriculum = load_curriculum()
        on_disk = load_authored_bank()
        async with _rollback_session() as session:
            for topic_id, expected in on_disk.items():
                exported = await build_bank_file(
                    session,
                    topic_id=topic_id,
                    curriculum_version=curriculum.curriculum_version,
                )
                assert exported.templates == expected, (
                    f"{topic_id}.yaml is out of date with the approved set in the database "
                    f"- run `make question-export` and commit the diff"
                )

    asyncio.run(run())


def test_export_round_trips_through_yaml_unchanged() -> None:
    """Rendering and re-parsing must be lossless, or the file is not the content."""
    bank = AuthoredBankFile(
        curriculum_version="2026.1", topic_id="linear_equations", templates=[_item()]
    )
    reparsed = AuthoredBankFile.model_validate(yaml.safe_load(render_bank_file(bank)))
    assert reparsed == bank


def test_loading_is_idempotent_and_lands_approved_and_servable() -> None:
    """A second load is a no-op, and what lands is immediately deliverable."""

    async def run() -> None:
        curriculum = load_curriculum()
        async with _rollback_session() as session:
            repo = QuestionRepository(session)
            item = _item()

            summary = LoadSummary()
            await _load_authored_templates(session, curriculum, item.topic_id, [item], summary)
            assert (summary.templates_created, summary.variants_created) == (1, 1)

            template = await repo.get_template(item.question_template_id)
            assert template is not None
            # Approved and active on arrival: the human approval happened before the
            # export, and the file is the record of it (D-026).
            assert template.validation_status == "approved"
            assert template.active_status == "active"
            assert template.authoring_mode == "authored"
            # The canonical variant is what D-189's serving path reads.
            variant = await repo.get_variant_for_template(item.question_template_id)
            assert variant is not None
            assert variant.rendered_question == item.rendered_question
            assert variant.correct_option == item.correct_option
            # Deliverable through the unchanged runtime selection query.
            active = await repo.get_active_questions(item.topic_id, difficulty=1)
            assert item.question_template_id in {t.question_template_id for t in active}

            again = LoadSummary()
            await _load_authored_templates(session, curriculum, item.topic_id, [item], again)
            assert (again.templates_created, again.templates_skipped_existing) == (0, 1)

    asyncio.run(run())


def test_an_edited_item_whose_answer_no_longer_matches_fails_the_load() -> None:
    """The reason the loader re-validates instead of trusting the file.

    Changing a correct answer without changing the options is the plausible hand-edit, and
    it is the one that would put a wrong answer in front of a student. The load aborts
    rather than inserting - same posture the shape bank's loader has.
    """

    async def run() -> None:
        curriculum = load_curriculum()
        async with _rollback_session() as session:
            broken = _item(
                question_template_id="authored-bank-test-broken",
                # Options still say 4; the expression now solves to 5.
                answer_expression="Eq(x + 3, 8)",
            )
            with pytest.raises(CurriculumLoadError) as excinfo:
                await _load_authored_templates(
                    session, curriculum, broken.topic_id, [broken], LoadSummary()
                )
            assert "does not match declared correct option" in str(excinfo.value)

            repo = QuestionRepository(session)
            assert await repo.get_template(broken.question_template_id) is None

    asyncio.run(run())


def test_difficulty_comes_from_the_field_not_the_id(tmp_path: Path) -> None:
    """D-235: the `d{n}` in a template id is provenance, and the tier is `difficulty_label`.

    Ids are minted once as `authored-{topic}-d{difficulty_label}-{seed}` and never
    recomputed, so re-tiering an item leaves the segment behind. D-235 re-tiered 16 items
    and kept every id, because the id is what attempt rows point at and renaming it would
    orphan a student's history to fix a string nothing reads.

    Both halves matter and both can fail. The first pins the round trip: an item whose id
    says 1 and whose field says 5 comes back as a 5. The second is the one that protects
    the rule going forward - it fails the day someone recovers a tier by parsing the id,
    which would quietly make every re-tiered item wrong in whatever they built on it.
    """
    stale = _item(question_template_id="authored-linear_equations-d1-990001", difficulty_label=5)
    bank = AuthoredBankFile(
        curriculum_version="2026.1", topic_id="linear_equations", templates=[stale]
    )
    (tmp_path / "linear_equations.yaml").write_text(render_bank_file(bank))

    (loaded,) = load_authored_bank(tmp_path)["linear_equations"]
    assert loaded.question_template_id == "authored-linear_equations-d1-990001"
    assert loaded.difficulty_label == 5

    # Nothing outside the tests may read the tier back out of the id. Written as a search
    # over the shipped source because the rule is about code that does not exist yet: the
    # ways to recover "5" from "authored-linear_equations-d5-306500" all take the
    # second-from-last dash-segment or split on the literal "-d".
    tier_from_id = re.compile(r"""rsplit\(["']-["'],\s*2\)|split\(["']-d["']\)|-d\(\\d""")
    repo_root = Path(__file__).resolve().parents[3]
    offenders = sorted(
        str(path.relative_to(repo_root))
        for path in repo_root.glob("**/src/**/*.py")
        if "authored-" in (source := path.read_text()) and tier_from_id.search(source)
    )
    assert not offenders, f"these parse a tier out of a template id: {offenders}"


def test_editing_an_item_already_in_the_database_propagates() -> None:
    """D-235: the load-time gate has to apply to edits, not only to first inserts.

    Two documents in this package disagreed about this. `authored_bank`'s module docstring
    says the file "is re-validated on load, not trusted", and that "editing a correct answer
    in the file without editing its options fails the load rather than reaching a student".
    `loader._load_authored_templates` skipped by id *before* validating, so both halves were
    true only for an item the environment had never seen. In a long-lived database - staging,
    and later production - an edit was silently discarded and the load still reported success.

    The consequence is not theoretical: D-235 re-tiered 16 items and `make curriculum-load`
    reported "127 already existed, 0 created". The file said one thing, every environment
    served another, and nothing anywhere said so.
    """

    async def run() -> None:
        curriculum = load_curriculum()
        async with _rollback_session() as session:
            repo = QuestionRepository(session)
            original = _item(question_template_id="authored-bank-test-edit", difficulty_label=1)
            await _load_authored_templates(
                session, curriculum, original.topic_id, [original], LoadSummary()
            )

            edited = _item(
                question_template_id="authored-bank-test-edit",
                difficulty_label=4,
                skill_id="linear_two_step",
            )
            summary = LoadSummary()
            await _load_authored_templates(
                session, curriculum, edited.topic_id, [edited], summary
            )

            row = await repo.get_template("authored-bank-test-edit")
            assert row is not None
            assert row.difficulty_label == 4, "the file's tier never reached the database"
            assert row.skill_id == "linear_two_step"
            assert summary.templates_updated == 1

            # And an edit that breaks the item must fail the load rather than be applied,
            # which is the half the skip made unreachable.
            broken = _item(
                question_template_id="authored-bank-test-edit",
                answer_expression="Eq(x + 3, 8)",
            )
            with pytest.raises(CurriculumLoadError):
                await _load_authored_templates(
                    session, curriculum, broken.topic_id, [broken], LoadSummary()
                )

    asyncio.run(run())


# Small integers spelled out. Only as far as twenty plus the round tens a K-3 word problem
# actually uses - a longer table would be guessing at text nobody has written.
_NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
    "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
}


def test_a_div_remainder_item_never_states_the_answer_to_its_own_division() -> None:
    """The skill is "Divide with remainders", so the stem may not do the dividing (D-238).

    Every one of these six items used to state either the remainder ("there are 2 badges
    left over") or the number of completed groups ("Three coaches are filled completely").
    With that sentence present the student subtracts a given number and divides exactly -
    no remainder is ever produced, and *not one item in the bank exercised the skill it was
    filed under*. The judge had been rating them flat at 3.00 across declared 4 and 5, which
    D-235 read as the instrument under-reading the topic and defended two of them against.

    The rule is deterministic and needs no model: **a `div_remainder` stem states exactly two
    distinct numbers**, the dividend and the divisor. A third one can only be the quotient or
    the remainder, which is the student's job. The first version of this test tried to be
    cleverer - identify the dividend as the largest number and the divisor as the smallest,
    then look for the quotient or remainder among the rest - and caught **one of the six**,
    because "the smallest number is the divisor" is exactly what stops being true once a
    remainder is also stated. Counting is both simpler and correct.

    **Number-words count.** Restricted to digits the check caught four of the six, because
    two of them wrote the giveaway out: "*Seven* rows are completed", "*Three* coaches are
    filled completely". A rule that reads `\\d+` only would have let the two worst offenders
    through - they are the ones that state the *quotient* rather than the remainder - and
    passed while claiming to cover the skill.

    Checked here rather than in `validate_authored_item` because it is a claim about one
    skill's semantics, and the §5.8.5 gate is deliberately topic-agnostic.
    """
    offenders = []
    for item in load_authored_bank().get("multiplication_division", []):
        if item.skill_id != "div_remainder":
            continue
        stated = {int(n) for n in re.findall(r"\d+", item.stem)}
        words = re.findall(r"[a-z]+", item.stem.lower())
        stated |= {_NUMBER_WORDS[w] for w in words if w in _NUMBER_WORDS}
        numbers = sorted(stated)
        if len(numbers) != 2:
            offenders.append(f"{item.question_template_id} states {numbers}")
    assert not offenders, (
        f"{len(offenders)} div_remainder item(s) state more than the dividend and divisor, "
        f"handing the student the result of the division their skill exists to practise: "
        f"{offenders}"
    )


def test_place_value_identify_is_not_authored_above_the_tier_its_ladder_reaches() -> None:
    """`place_value`'s anchors say `identify` has no tier-5 work; the bank must agree (D-238).

    Measured over four runs and 100 judgements, `place_value_identify` sat flat at 1.69-2.25
    across all five declared tiers while `place_value_compare` climbed 2.50 -> 3.38 -> 3.67 -
    because tiers 4 and 5 each led with a bare digit-count clause. Reading one digit's place
    is the same task at 47 and at 30,502, so the extra digits bought a tier number and no
    work, and the pooled d4 rung came out *below* d3 because it held both skills at once.

    A rubric claiming a range its skill does not have is not a cosmetic problem: the tier is
    what `mastery_bootstrap` routes on, so a decorative tier still decides what a real
    student is served next.
    """
    too_high = [
        item.question_template_id
        for item in load_authored_bank().get("place_value", [])
        if item.skill_id == "place_value_identify" and item.difficulty_label > 4
    ]
    assert not too_high, (
        f"place_value_identify items authored above tier 4, which its half of the anchor "
        f"ladder explicitly does not reach: {too_high}"
    )
