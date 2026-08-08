import asyncio
import pathlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from intellichoice_curriculum.authored_bank import load_authored_bank
from intellichoice_curriculum.loader import TEMPLATE_BANKS, load_curriculum_and_templates
from intellichoice_db.engine import create_engine
from intellichoice_db.repositories.curriculum import CurriculumRepository
from intellichoice_db.repositories.questions import QuestionRepository
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def _postgres_skip_reason() -> str | None:
    """Mirrors packages/db/tests/conftest.py's probe (D-008/D-013 style), inlined
    here rather than shared: pytest's importlib import-mode names test-package
    conftest modules by their directory, and this repo already has a
    packages/db/tests package, so a same-named tests/conftest.py collides.
    """

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


pytestmark = pytest.mark.skipif(
    (_reason := _postgres_skip_reason()) is not None, reason=_reason or ""
)


def _expected_template_count() -> int:
    """Everything `load_curriculum_and_templates` is responsible for: the hand-authored
    shape banks plus the approved authored items exported to `curriculum/internal_math/
    authored/` (D-190). Reads the same sources the loader does, so content changes move
    both together.
    """
    shape = sum(len(templates) for templates in TEMPLATE_BANKS.values())
    authored = sum(len(templates) for templates in load_authored_bank().values())
    return shape + authored


def test_loading_curriculum_produces_the_expected_final_state() -> None:
    async def run() -> None:
        async with _rollback_session() as session:
            summary = await load_curriculum_and_templates(session)

            # Idempotent by natural key: whether this call creates rows or finds
            # them already loaded (e.g. from a prior `make curriculum-load` run
            # against this same dev DB) depends on prior state - what must always
            # hold is the created+skipped total and the resulting data shape.
            #
            # Derived from the banks rather than written as a literal (D-190). It was 50,
            # and adding five authored items broke it - the third time in this file that a
            # count coupled the loader's contract to how much content exists. The loader
            # promises to load *its banks*; how big they are is content's business.
            assert (
                summary.templates_created + summary.templates_skipped_existing
                == _expected_template_count()
            )

            curriculum_repo = CurriculumRepository(session)
            topic = await curriculum_repo.get_topic("linear_equations")
            assert topic is not None
            assert topic.name == "Linear Equations"

            question_repo = QuestionRepository(session)
            # Identity, not size (D-187). This used to assert `len(active) == 10`, which made
            # the loader's contract a claim about *everything* approved at this tier - so
            # approving one authored template broke it, exactly as S20's live verification
            # found. What the loader actually promises is that its own deterministically-named
            # bank is loaded; the authored pipeline (D-186) adds to this same topic and
            # difficulty and must be able to without touching this test.
            #
            # D-210 moved this from `get_active_questions` to `get_templates`. The loader's
            # promise is *loaded*, and that is unchanged; what changed is that the serving
            # path no longer hands shape templates to a student, so asking the serving query
            # about them would now be asking the wrong question. `test_shape_templates_are_
            # loaded_but_never_served` below pins the other half.
            hand_authored = {f"linear_equations-d1-{index:02d}" for index in range(10)}
            loaded = await question_repo.get_templates(sorted(hand_authored))
            assert set(loaded) == hand_authored

            served = await question_repo.get_active_questions("linear_equations", difficulty=1)
            assert not (hand_authored & {t.question_template_id for t in served}), (
                "a bare-equation shape template reached the serving path (D-210)"
            )
            assert all(t.authoring_mode == "authored" for t in served), (
                "the serving path returned a non-authored template"
            )

    asyncio.run(run())


def test_loader_is_idempotent() -> None:
    async def run() -> None:
        async with _rollback_session() as session:
            await load_curriculum_and_templates(session)
            second = await load_curriculum_and_templates(session)

            assert second.topics_created == 0
            assert second.skills_created == 0
            assert second.templates_created == 0
            assert second.templates_skipped_existing == _expected_template_count()

    asyncio.run(run())


def test_loader_rejects_a_template_that_fails_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    from intellichoice_curriculum import loader
    from intellichoice_curriculum.templates.model import QuestionTemplateDef
    from intellichoice_curriculum.validation import ValidationResult

    def _always_fails(*args: object, **kwargs: object) -> object:
        result = ValidationResult()
        result.fail("forced failure for this test")
        return result

    monkeypatch.setattr(loader, "validate_variant", _always_fails)
    # A synthetic topic_id guarantees this template can never already exist in the
    # DB (unlike the real linear_equations bank, which `make curriculum-load` may
    # have already persisted), so the loader is forced to actually attempt it.
    monkeypatch.setattr(
        loader,
        "TEMPLATE_BANKS",
        {
            "zzz_test_topic_never_loaded": [
                QuestionTemplateDef(
                    topic_id="linear_equations",
                    skill_id="linear_one_step",
                    grade_band="6-7",
                    difficulty_label=1,
                    parameter_schema={"b": {"min": 1, "max": 9}, "x": {"min": 1, "max": 9}},
                    solution_function="one_step_add",
                    correct_option_generator="format_integer",
                    distractor_generators=[
                        "distractor_sign_flip",
                        "distractor_off_by_one",
                        "distractor_scaled",
                    ],
                    estimated_time_seconds=25,
                )
            ]
        },
    )

    async def run() -> None:
        async with _rollback_session() as session:
            with pytest.raises(loader.CurriculumLoadError):
                await load_curriculum_and_templates(session)

    asyncio.run(run())


def test_every_item_in_every_bank_file_is_active_after_a_load() -> None:
    """D-222: the retirement pass must not reach across topics.

    `get_authored_templates()` is deliberately unfiltered, so before this the per-topic
    retirement retired everything the *other* topic's file did not list. The failure only
    became reachable the day a second bank file existed: loading `fraction_operations`
    retired all of `linear_equations`, then loading `linear_equations` retired all of
    `fraction_operations`, and one `make curriculum-load` left no servable question in any
    environment - `_servable()` filters on `active_status`.

    Asserted as "every id the files list is active", which is the contract D-210 actually
    states (the bank file decides what is servable) rather than a count that content
    changes would break.
    """

    async def run() -> None:
        async with _rollback_session() as session:
            await load_curriculum_and_templates(session)
            repo = QuestionRepository(session)
            by_id = {t.question_template_id: t for t in await repo.get_authored_templates()}

            banks = load_authored_bank()
            assert len(banks) >= 2, (
                "this test is only meaningful with more than one authored bank file"
            )
            retired = []
            for topic_id, templates in banks.items():
                for template in templates:
                    row = by_id.get(template.question_template_id)
                    assert row is not None, (topic_id, template.question_template_id)
                    if row.active_status != "active":
                        retired.append((topic_id, template.question_template_id))
            assert not retired, (
                "a load retired items their own bank file still lists: " f"{retired[:10]}"
            )

    asyncio.run(run())


def test_no_approved_item_is_a_bare_equation() -> None:
    """D-210: every served question must read as a situation, not as an equation.

    The `authoring_mode` filter in `QuestionRepository` retires the *shape* bank, but it
    cannot catch this: five of the forty-eight approved **authored** items were themselves
    bare equations - `Solve for x: 2x + 7 = 19` and one sibling per difficulty tier,
    evidently the original seeds from before D-186 taught the pipeline to write word
    problems. They passed every gate because nothing ever asked them to be contextual, and
    a pinned pre-exam capture caught one of them still being served after the filter went
    in.

    Asserted over the YAML rather than the database because the YAML is the source of
    truth that every environment loads from; a database can also hold rows an older bank
    inserted, which is a separate cleanup and not something a test can do.

    The heuristic is deliberately narrow - an imperative opener *and* very little prose.
    "Solve for the number of weeks Maya has been saving" is a legitimate word problem and
    must not trip this.

    Over *every* bank file, not just `linear_equations` (D-222). A rule about what a
    student may be shown does not belong to one topic, and the topic added second is
    exactly the one nothing would have been checking.
    """
    import re

    import yaml

    authored_dir = (
        pathlib.Path(__file__).resolve().parents[3] / "curriculum/internal_math/authored"
    )
    paths = sorted(authored_dir.glob("*.yaml"))
    assert paths, f"no authored bank files found under {authored_dir}"
    offenders = []
    for path in paths:
        bank = yaml.safe_load(path.read_text())
        for template in bank["templates"]:
            stem = template["stem"].strip()
            prose_words = re.findall(
                r"[A-Za-z]{3,}", (template.get("context_block") or "") + stem
            )
            if re.match(r"^(solve|find|evaluate|simplify|what is)\b", stem, re.I) and len(
                prose_words
            ) < 12:
                offenders.append((template["question_template_id"], stem[:60]))

    assert not offenders, (
        "approved items read as bare equations rather than as situations: "
        f"{offenders}"
    )
