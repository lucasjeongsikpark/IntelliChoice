"""The C1 coverage matrix stays true to its source (D-273, Phase 0).

`docs/CONTENT_COVERAGE.md` claims every row of the source taxonomy is dispositioned. That
claim is only worth something if a row added to the CSV, or a disposition quietly dropped,
*fails* rather than passing silently - "unverified counts as not traced", the posture
TRACEABILITY.md takes for SPEC requirements, applied to content.

These are pure file reads: no model call, no database, no network.
"""

import csv
import importlib.util
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[3]
SOURCE = ROOT / "knowledge-content" / "intellichoice_math_topics.csv"
MATRIX = ROOT / "curriculum" / "coverage" / "csv_row_dispositions.csv"
BUILDER = ROOT / "scripts" / "build_content_coverage.py"


def _load_builder():
    spec = importlib.util.spec_from_file_location("build_content_coverage", BUILDER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def matrix_rows() -> list[dict[str, str]]:
    return list(csv.DictReader(MATRIX.open()))


@pytest.fixture(scope="module")
def source_rows() -> list[dict[str, str]]:
    return list(csv.DictReader(SOURCE.open()))


def test_every_source_row_has_a_disposition(matrix_rows, source_rows):
    """The whole point of the matrix. A row added to the CSV without a decision about it
    lands here as a length mismatch rather than as silent absence from the plan.
    """
    assert len(matrix_rows) == len(source_rows)
    for matrix_row, source_row in zip(matrix_rows, source_rows, strict=True):
        assert matrix_row["topic"] == source_row["topic"]
        assert matrix_row["book"] == source_row["book"]
        assert matrix_row["answer_model"], f"row {matrix_row['row_index']} undispositioned"


def test_every_answer_model_is_one_the_plan_knows_how_to_handle(matrix_rows):
    """A typo in a disposition would otherwise create a family nothing plans for."""
    builder = _load_builder()
    for row in matrix_rows:
        assert row["answer_model"] in builder.FAMILIES
        expected_family, _ = builder.FAMILIES[row["answer_model"]]
        assert row["family"] == expected_family


def test_skill_ids_are_unique_because_they_are_book_qualified(matrix_rows):
    """Only 194 of the 246 topic strings are distinct - `Fractions` appears in seven
    different books - so an unqualified slug would merge unrelated skills. This is the
    test that would have caught that, and it is why `skill_id` carries the book.
    """
    unique = [r for r in matrix_rows if not r["duplicate_of_earlier_row"]]
    skill_ids = [r["skill_id"] for r in unique]
    assert len(set(skill_ids)) == len(skill_ids)


def test_the_coverage_denominator_is_245_not_246(matrix_rows):
    """`('6', 'Grade 6 Fractions', 'Three Fractions')` appears twice in the source. Every
    percentage in CONTENT_COVERAGE.md is computed against the unique count, so the
    duplicate has to stay flagged rather than quietly counted or quietly deleted.
    """
    assert len(matrix_rows) == 246
    duplicates = [r for r in matrix_rows if r["duplicate_of_earlier_row"]]
    assert len(duplicates) == 1
    assert duplicates[0]["topic"] == "Three Fractions"
    assert duplicates[0]["book"] == "Grade 6 Fractions"


def test_the_matrix_matches_what_the_builder_would_regenerate(tmp_path, monkeypatch):
    """The committed matrix is a build artifact, so a hand edit to it - or a change to the
    source CSV without a rebuild - is drift. Same posture as
    `test_the_repo_bank_file_matches_what_the_database_would_export`.
    """
    builder = _load_builder()
    regenerated = tmp_path / "csv_row_dispositions.csv"
    monkeypatch.setattr(builder, "OUT", regenerated)
    builder.main()
    assert regenerated.read_text() == MATRIX.read_text()


def test_family_rollups_match_the_numbers_the_doc_quotes(matrix_rows):
    """CONTENT_COVERAGE.md and ROADMAP C1 both quote these counts, and the phase ordering
    was decided on them. If a re-disposition moves a row between families, the docs quoting
    the old split should fail rather than drift.
    """
    unique = [r for r in matrix_rows if not r["duplicate_of_earlier_row"]]
    counts: dict[str, int] = {}
    for row in unique:
        counts[row["family"]] = counts.get(row["family"], 0) + 1
    assert counts == {"A": 173, "B": 37, "C": 34, "D": 1}
    assert sum(counts.values()) == 245


def test_algebra_i_is_entirely_blocked_on_the_router(matrix_rows):
    """The single finding that moved the router ahead of seeding: not one row of Algebra I
    can be authored by the pipeline as it stands. If a future re-disposition changes that,
    the phase ordering deserves to be revisited rather than inherited.
    """
    algebra_i = [r for r in matrix_rows if r["book"] == "Algebra I"]
    assert len(algebra_i) == 6
    assert all(r["family"] == "B" for r in algebra_i)
