"""AUD-F-31: the SQL shape of the `select_topic` hot path (SPEC §5.9.1-§5.9.2 build).

The staging X-Ray profile (D-129 §5) measured `langgraph.select_topic` at 1.62 s, of which
1.624 s was 51 sequential SQL statements and *no* Bedrock call - an N+1 write pattern over
the 10 exam items. This file is the local, repeatable version of that measurement plus the
two properties a batching refactor must not break: the exam's structure (§5.9.1) and its
determinism for a fixed seed (CLAUDE.md non-negotiable #2 - the builder is deterministic
core, so the same seed must always build the same exam).

**The counter is checked before it is trusted.** Three sessions in a row the measuring
apparatus was wrong before the finding was (D-104 §8, D-121's alarm window, D-129 §5's
double-counted X-Ray segments), so `test_statement_counter_control` proves both directions:
that N separate executes count as N, and - the whole point of this refactor - that one
`executemany` carrying many rows counts as *one* statement with many parameter sets. A
counter that could not tell those apart could not evidence the change it is here to
evidence.

Real Postgres via a rollback session (D-013); no MySQL, because the builder is called
directly rather than through the attendance gate.
"""

import asyncio
import random
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

import pytest
from intellichoice_curriculum.loader import load_curriculum_and_templates
from intellichoice_db.engine import create_engine, create_session_factory, session_scope
from intellichoice_db.repositories.assessment import AssessmentRepository
from intellichoice_db.repositories.questions import QuestionRepository
from learning_api.services import flow
from learning_api.services.assessment_builder import (
    DIFFICULTIES,
    QUESTIONS_PER_DIFFICULTY,
    build_post_exam,
    build_pre_exam,
)
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession

TOPIC_ID = "linear_equations"
STUDENT_ID = "sql-shape-test-student"
SEED = 20260730


def _postgres_skip_reason() -> str | None:
    async def check() -> str | None:
        engine = create_engine()
        try:
            async with engine.connect() as conn:
                try:
                    await conn.execute(text("SELECT 1 FROM question_templates LIMIT 1"))
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


@pytest.fixture(scope="module", autouse=True)
def seeded_curriculum() -> None:
    """The template bank must exist and be committed - the rollback session below reads it."""

    async def load() -> None:
        engine = create_engine()
        try:
            session_factory = create_session_factory(engine)
            async with session_scope(session_factory) as session:
                await load_curriculum_and_templates(session)
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(load())


# Transaction-control statements the *test harness* issues, not the code under measurement:
# `join_transaction_mode="create_savepoint"` wraps each rollback session in a SAVEPOINT, and
# every nested flush releases one. They are excluded from the data-statement count and listed
# separately rather than dropped, because a count is only as honest as its denominator
# (D-129's coverage-control lesson at a much smaller scale).
_TRANSACTION_CONTROL = (
    "SAVEPOINT",
    "RELEASE SAVEPOINT",
    "ROLLBACK TO SAVEPOINT",
    "BEGIN",
    "COMMIT",
)


def _is_transaction_control(sql: str) -> bool:
    return sql.strip().upper().startswith(_TRANSACTION_CONTROL)


@dataclass
class StatementLog:
    """One entry per cursor execute - i.e. per database round-trip."""

    executes: list[tuple[str, int]] = field(default_factory=list)

    def data_executes(self) -> list[tuple[str, int]]:
        return [(sql, n) for sql, n in self.executes if not _is_transaction_control(sql)]

    def count(self, *, containing: str | None = None) -> int:
        """Data round-trips only. Pass `containing` to count one statement shape."""
        entries = self.data_executes()
        if containing is None:
            return len(entries)
        return sum(1 for sql, _ in entries if containing in sql)

    # No row-count accessor, deliberately. `len(parameters)` at this hook means two
    # different things: a raw `executemany` arrives as a list of parameter *sets* (so the
    # length is the row count), while the ORM's insertmanyvalues path arrives as one
    # flattened tuple (so a 10-row insert into an 11-column table reads 110). The first
    # draft of this file exposed that number as `rows()` and its control assertion passed
    # only because the control table happened to have exactly one column - a metric that
    # is right for the wrong reason is worse than no metric. The claim here is about
    # statement counts; that a batched INSERT really carries ten rows is proven
    # independently by `test_pre_exam_structure_...` counting the rows it wrote.

    def summary(self) -> str:
        lines = [
            f"{'  (txn) ' if _is_transaction_control(sql) else '        '}"
            f"{' '.join(sql.split())[:96]}"
            for sql, _params in self.executes
        ]
        control = len(self.executes) - self.count()
        return (
            f"{self.count()} data executes (+{control} harness transaction-control)\n"
            + "\n".join(lines)
        )


@asynccontextmanager
async def _counted_rollback_session() -> AsyncIterator[tuple[AsyncSession, StatementLog]]:
    log = StatementLog()
    engine = create_engine()
    try:
        async with engine.connect() as conn:
            sync_conn = conn.sync_connection
            assert sync_conn is not None

            def _record(
                _conn: object,
                _cursor: object,
                statement: str,
                parameters: object,
                _context: object,
                executemany: bool,
            ) -> None:
                sets = len(parameters) if executemany and parameters is not None else 1  # type: ignore[arg-type]
                log.executes.append((statement, sets))

            event.listen(sync_conn, "before_cursor_execute", _record)
            trans = await conn.begin()
            session = AsyncSession(bind=conn, join_transaction_mode="create_savepoint")
            try:
                yield session, log
            finally:
                await session.close()
                await trans.rollback()
                event.remove(sync_conn, "before_cursor_execute", _record)
    finally:
        await engine.dispose()


def _run(coro_fn) -> None:  # type: ignore[no-untyped-def]
    asyncio.run(coro_fn())


@pytest.fixture(autouse=True)
def _no_leftover_rows() -> Iterator[None]:
    """Belt and braces: every test here rolls back, but `STUDENT_ID` is not one of the
    MySQL-fixture ids the directory-wide sweep in `conftest.py` covers, so a future test
    that forgets the rollback session would otherwise leave rows behind.
    """
    yield

    async def sweep() -> None:
        engine = create_engine()
        try:
            async with engine.connect() as conn:
                await conn.execute(
                    text(
                        "DELETE FROM assessment_item_state WHERE assessment_item_id IN "
                        "(SELECT assessment_item_id FROM assessment_items "
                        "WHERE assessment_session_id IN (SELECT assessment_session_id FROM "
                        "assessment_sessions WHERE student_external_id = :sid))"
                    ),
                    {"sid": STUDENT_ID},
                )
                await conn.execute(
                    text(
                        "DELETE FROM assessment_items WHERE assessment_session_id IN "
                        "(SELECT assessment_session_id FROM assessment_sessions "
                        "WHERE student_external_id = :sid)"
                    ),
                    {"sid": STUDENT_ID},
                )
                await conn.execute(
                    text("DELETE FROM assessment_sessions WHERE student_external_id = :sid"),
                    {"sid": STUDENT_ID},
                )
                await conn.commit()
        finally:
            await engine.dispose()

    asyncio.run(sweep())


# --------------------------------------------------------------------------------------
# The instrument, checked first.
# --------------------------------------------------------------------------------------


def test_statement_counter_control() -> None:
    """Both directions: separate executes count separately, and one `executemany` carrying
    many rows counts as ONE round-trip with many parameter sets. The second half is the
    property the whole AUD-F-31 claim rests on.
    """

    async def scenario() -> None:
        async with _counted_rollback_session() as (session, log):
            await session.execute(text("SELECT 1"))
            await session.execute(text("SELECT 2"))
            assert log.count() == 2, log.summary()
            # The harness's own SAVEPOINT is observed but not counted as a data statement.
            # It showed up on this test's first run, which is why the exclusion is named.
            assert any(_is_transaction_control(sql) for sql, _ in log.executes), log.summary()

            await session.execute(
                text(
                    "CREATE TEMPORARY TABLE counter_control (n integer, label text) ON COMMIT DROP"
                )
            )
            before = log.count()
            await session.execute(
                text("INSERT INTO counter_control (n, label) VALUES (:n, :label)"),
                [{"n": 1, "label": "a"}, {"n": 2, "label": "b"}, {"n": 3, "label": "c"}],
            )
            # Three rows in ONE round-trip counts as one statement. This is the property
            # the whole AUD-F-31 measurement rests on: if a batched insert of many rows
            # counted as many statements, a 47 -> 7 reading would mean nothing.
            assert log.count() - before == 1, log.summary()
            assert log.count(containing="INSERT INTO counter_control") == 1, log.summary()

    _run(scenario)


# --------------------------------------------------------------------------------------
# The measurement.
# --------------------------------------------------------------------------------------


async def _build_and_view(session: AsyncSession, rng: random.Random) -> list[flow.QuestionItemView]:
    """The Postgres half of the `select_topic` node: build the pre-exam, then read it back
    for the response payload exactly as `graph/nodes.py:select_topic` does.
    """
    question_repo = QuestionRepository(session)
    assessment_repo = AssessmentRepository(session)
    pre_exam = await build_pre_exam(
        question_repo=question_repo,
        assessment_repo=assessment_repo,
        student_external_id=STUDENT_ID,
        topic_id=TOPIC_ID,
        rng=rng,
    )
    items = await assessment_repo.get_items(pre_exam.assessment_session_id)
    return await flow.items_view(question_repo, items)


# The Postgres half of `select_topic` after AUD-F-31's batching. Measured, not aspirational:
# 47 before, and the 47 reconciled with the staging X-Ray profile's 51 (the missing four are
# the router's `SELECT topics`, the attendance gate's MySQL-side read, and two
# connection-level statements, none of which this test drives).
# Both were 7 until authored templates became servable (D-189) and versioned (D-190). The
# eighth statement is the canonical-variant read: an authored template's content lives on
# its variant rather than in a shape function, so a build whose candidate pool contains one
# has to fetch it.
#
# **It is one statement, not one per item, and that is the property being guarded here.**
# The read is issued once before the sampling loop, over the whole candidate pool - the
# obvious alternative (fetch per sampled template) would be an N+1 of exactly the kind
# AUD-F-31 measured and removed. It is skipped entirely for a topic with no
# statically-rendered templates, so these numbers are a function of the seeded bank; they
# hold in every environment because the bank is now loaded from the repository rather than
# approved per-database.
_PRE_EXAM_PATH_BUDGET = 8
_POST_EXAM_BUILD_BUDGET = 8

# Every statement shape the exam build issues, and how many round-trips each may take. The
# point of asserting per shape rather than only on the total: a total can be met while one
# table quietly goes back to N+1 and another gets cheaper.
_PRE_EXAM_SHAPE_BUDGET = {
    "INSERT INTO assessment_sessions": 1,
    "SELECT question_templates": 1,
    # One for the canonical-variant read, one for `items_view` reading back what it just
    # wrote. Asserted now that there are two, because "how many times do we read variants"
    # is exactly the count that used to be ten.
    "SELECT question_variants": 2,
    "INSERT INTO question_variants": 1,
    "INSERT INTO assessment_items": 1,
    "INSERT INTO assessment_item_state": 1,
}


def test_pre_exam_path_issues_a_constant_number_of_statements() -> None:
    """AUD-F-31's regression guard. Every write here used to be its own round-trip: 30 of
    the 47 statements were three per item over ten items, and ten more were `items_view`
    re-reading each variant one at a time.

    Asserted as an exact count rather than an upper bound, because this path is the p95
    driver of the whole learning app in every load run since D-121 - a statement added here
    should have to be deliberate enough to update a number.
    """

    async def scenario() -> None:
        async with _counted_rollback_session() as (session, log):
            views = await _build_and_view(session, random.Random(SEED))
            assert len(views) == len(DIFFICULTIES) * QUESTIONS_PER_DIFFICULTY
            for shape, allowed in _PRE_EXAM_SHAPE_BUDGET.items():
                assert log.count(containing=shape) == allowed, (
                    f"{shape}: expected {allowed}\n{log.summary()}"
                )
            assert log.count() == _PRE_EXAM_PATH_BUDGET, log.summary()

    _run(scenario)


def test_post_exam_build_issues_a_constant_number_of_statements() -> None:
    """The post-exam builder had the same N+1 shape plus two extra reads per item (the
    pre-exam variant and its template), which is why it measured 52.
    """

    async def scenario() -> None:
        async with _counted_rollback_session() as (session, log):
            question_repo = QuestionRepository(session)
            assessment_repo = AssessmentRepository(session)
            pre_exam = await build_pre_exam(
                question_repo=question_repo,
                assessment_repo=assessment_repo,
                student_external_id=STUDENT_ID,
                topic_id=TOPIC_ID,
                rng=random.Random(SEED),
            )
            before = log.count()
            await build_post_exam(
                question_repo=question_repo,
                assessment_repo=assessment_repo,
                student_external_id=STUDENT_ID,
                pre_assessment_session_id=pre_exam.assessment_session_id,
                rng=random.Random(SEED + 1),
            )
            assert log.count() - before == _POST_EXAM_BUILD_BUDGET, log.summary()

    _run(scenario)


# --------------------------------------------------------------------------------------
# The properties the refactor must preserve.
# --------------------------------------------------------------------------------------


def test_pre_exam_structure_is_two_items_per_difficulty_in_display_order() -> None:
    """SPEC §5.9.1: a fixed set of `QUESTIONS_PER_DIFFICULTY` per difficulty, ordered, each
    item carrying an `unseen` state row (§5.9/§5.13 nav bookkeeping).
    """

    async def scenario() -> None:
        async with _counted_rollback_session() as (session, _log):
            question_repo = QuestionRepository(session)
            assessment_repo = AssessmentRepository(session)
            pre_exam = await build_pre_exam(
                question_repo=question_repo,
                assessment_repo=assessment_repo,
                student_external_id=STUDENT_ID,
                topic_id=TOPIC_ID,
                rng=random.Random(SEED),
            )
            items = await assessment_repo.get_items(pre_exam.assessment_session_id)
            expected = len(DIFFICULTIES) * QUESTIONS_PER_DIFFICULTY
            assert len(items) == expected
            assert [item.display_order for item in items] == list(range(expected))

            states = await assessment_repo.get_item_states(pre_exam.assessment_session_id)
            assert len(states) == expected
            assert {state.status for state in states} == {"unseen"}
            assert {state.assessment_item_id for state in states} == {
                item.assessment_item_id for item in items
            }

            by_difficulty: dict[int, int] = {}
            for item in items:
                variant = await question_repo.get_variant(item.question_variant_id)
                assert variant is not None
                template = await question_repo.get_template(variant.question_template_id)
                assert template is not None
                assert template.topic_id == TOPIC_ID
                assert template.active_status == "active"
                assert template.validation_status == "approved"
                by_difficulty[template.difficulty_label] = (
                    by_difficulty.get(template.difficulty_label, 0) + 1
                )
            assert by_difficulty == {d: QUESTIONS_PER_DIFFICULTY for d in DIFFICULTIES}

    _run(scenario)


def _content(views: list[flow.QuestionItemView]) -> list[tuple[str, str, str, str, str]]:
    """What the student actually sees, in display order."""
    return [
        (v.rendered_question, v.option_a, v.option_b, v.option_c, v.option_d)
        for v in sorted(views, key=lambda v: v.display_order)
    ]


# Captured at `SEED`, so a refactor is held to producing the *same exam*, not merely a
# valid one. A batching change that reorders the template list a seeded `rng.sample()`
# consumes would still build ten well-formed questions - these literals are what makes that
# failure visible.
#
# **Re-pinned 2026-08-05 (D-190), and the distinction matters.** The five approved authored
# items are now loaded from `curriculum/internal_math/authored/linear_equations.yaml`, so
# the candidate pool at each difficulty went from 10 to 11 and a seeded `rng.sample()`
# legitimately picks differently. This fixture guards *refactors*, not the bank's contents.
#
# D-189 tried this same re-pin one commit too early, when the content existed only in one
# developer's database - CI failed, correctly, because the capture described a bank nobody
# else had. It holds now for the reason it did not then: the content is in the repository,
# so every environment builds the same exam from the same seed. That is the difference
# between re-pinning a fixture and encoding local state into it. Original capture: `c736dc6`.
#
# The third row is the tell: `2x + 7 = 19` with options 6/8/9/13 is
# `authored-linear_equations-d2-9200`, an authored item served from its canonical variant.
# Re-pinned 2026-08-06 (D-206): the approved bank grew from 5 authored items to 48, so
# the same seed draws from a much larger pool and builds a different exam. Legitimate
# for the reason stated above - the content is in the repository, so every environment
# builds this same exam. The fourth row is the tell: an authored word problem where the
# previous capture's authored item was `d2-9200`. Verified by hand - $8 saved plus $5 a
# week reaching $48 is 8 + 5w = 48, so w = 8, and option d is 8.
# Pinned verbatim, so the rows are not wrapped: reformatting captured content is a way
# to change what is being pinned without noticing.
# D-215 re-captured this. AUD-F-31 pinned it to prove a *refactor* left content untouched,
# which it still does - but the walk of the deployed UI found 13 items whose context block was
# reviewer meta-commentary or a restatement of the stem, and 2 that should not be served at all
# (a duplicate pair, and one problem that compares a relative quantity against an absolute one).
# Stripping and retiring those changes which items this seed draws, so the old capture pinned
# content that no longer exists. Regenerated from the bank rather than hand-edited.
# D-217 re-captured one row again: a *served study item* was found with the same context-block
# leak ("This is a concrete real-world scenario requiring students to set up and solve..."),
# missed by D-215's sweep. Stripping it re-mints the item under a new id/seed, which reshuffles
# the difficulty-3 draw, so index 5 is now the two-gardeners problem instead of the arcade item.
# Regenerated from the bank, not hand-edited.
_PINNED_PRE_EXAM_AT_SEED: tuple[tuple[str, str, str, str, str], ...] = (
    (
        "Liam’s father is filling a large fish tank for a community event. The tank already has some water in it, and he adds more every day.\n\nLiam’s father is preparing a fish tank for a community event. The tank already has 30 litres of water. He adds 5 litres of water every day. How many days will it take for the tank to have 70 litres?",  # noqa: E501
        "10",
        "6",
        "8",
        "14",
    ),
    (
        "Liam has a lemonade stand. He starts the day with 15 cups of lemonade. By the end of the day, he has sold 7 cups. He wants to know how many cups he needs to make tonight so he will have exactly 20 cups ready for tomorrow. How many cups should he make?",  # noqa: E501
        "5",
        "12",
        "2",
        "8",
    ),
    (
        "Jamal starts with $60 and spends $4 each week on snacks. He wants to know how many weeks it will take until he has only $12 left.",  # noqa: E501
        "3",
        "12",
        "8",
        "15",
    ),
    (
        "Liam earns $5 each week by helping his neighbour with gardening. He already has $8 saved from his birthday. After a few weeks, he checks his savings and finds he has $48 in total. How many weeks has Liam been saving?",  # noqa: E501
        "6",
        "10",
        "9",
        "8",
    ),
    (
        "Marcus is training for a race. He runs 3 kilometers every morning and has already run 27 kilometers this month. His goal is to run 48 kilometers total. How many more mornings must he run to reach his goal?",  # noqa: E501
        "7 mornings",
        "12 mornings",
        "5 mornings",
        "9 mornings",
    ),
    (
        "Two gardeners are planting flowers along a path. Asha plants 3 flowers per minute and started with 5 already planted. Jasmine plants 2 flowers per minute and started with 11 already planted. After how many minutes will they have planted the same total number of flowers?",  # noqa: E501
        "4 minutes",
        "6 minutes",
        "8 minutes",
        "10 minutes",
    ),
    (
        "A café is mixing two types of coffee. They pour 8 liters of cold brew and add hot coffee until the total is 3 times the cold brew amount. How many liters of hot coffee did they add?",  # noqa: E501
        "8",
        "24",
        "32",
        "16",
    ),
    (
        "Lena is sewing ribbon onto a dance banner for the school festival. She already has 3/4 metres of ribbon sewn on. Each day, she adds another 1/8 metre of ribbon. The banner needs a total of 3 metres of ribbon. How many days will it take Lena to finish the banner?",  # noqa: E501
        "18",
        "12",
        "6",
        "-6",
    ),
    (
        "Maya has two options for earning money. Option 1: She starts with $6 and earns $4 each week. Option 2: She starts with $18 and earns $2 each week. After how many weeks will she have the same amount of money under both options?",  # noqa: E501
        "4 weeks",
        "3 weeks",
        "6 weeks",
        "12 weeks",
    ),
    (
        "Leo packs 2 identical boxes. Each box holds 4 more items than the size of Mia’s group, plus he adds 1 loose item. Mia packs 3 groups of items, each the size of her group, and adds 3 loose items. They end up with the same number of items. How many items are in one of Mia’s groups?",  # noqa: E501
        "10",
        "4",
        "6",
        "5",
    ),
)


def test_pre_exam_content_matches_the_pre_refactor_capture() -> None:
    """AUD-F-31's content-preservation check: the seed that built this exam before the
    batching refactor must still build exactly it.
    """

    async def scenario() -> None:
        async with _counted_rollback_session() as (session, _log):
            built = _content(await _build_and_view(session, random.Random(SEED)))
        assert tuple(built) == _PINNED_PRE_EXAM_AT_SEED

    _run(scenario)


def test_pre_exam_build_is_deterministic_for_a_fixed_seed() -> None:
    """CLAUDE.md non-negotiable #2: the builder is deterministic core, so two builds from
    equally-seeded RNGs must produce the same questions in the same order.

    This is the test that makes batching the per-difficulty template reads safe. Collapsing
    five queries into one changes the row order `rng.sample()` consumes, and row order is
    what decides *which* templates a seed picks - so the batched read has to impose an
    explicit order rather than inherit whatever Postgres returns.
    """

    async def scenario() -> None:
        async with _counted_rollback_session() as (session, _log):
            first = _content(await _build_and_view(session, random.Random(SEED)))
        async with _counted_rollback_session() as (session, _log):
            second = _content(await _build_and_view(session, random.Random(SEED)))
        assert first == second
        # A different seed must actually produce different questions, or the assertion
        # above would pass for a builder that ignores its RNG entirely.
        async with _counted_rollback_session() as (session, _log):
            other = _content(await _build_and_view(session, random.Random(SEED + 1)))
        assert other != first

    _run(scenario)
