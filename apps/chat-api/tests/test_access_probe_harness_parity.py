"""AUD-C-25 / D-179: the access-probe measurement harness must *call* the shipped rule.

The sibling guard (`test_qa_coverage_runner_config_parity.py`) checks that the paid eval
passes the same `Settings` fields the route does - a guard on the harness's **inputs**.
This one is the level above it: `scripts/measure_access_probe_rules.py` chose every
access-probe constant since D-165, and until D-179 its "chosen" column was a
*reimplementation* of the rule (`rerank_prefloor_margin_hint`) rather than
`probe_access` itself. Two divergences had accumulated unnoticed:

  1. the transcription checks the relevance floor before the tier margin, while
     `probe_access` checks the margin first;
  2. no rule in that file modelled `_lexical_only` at all, so production's keyword
     fallback was scored as silence.

(2) was not academic. Replaying D-177's dumps found 18 of 58 cases (human arm) whose
candidate pool is *empty* at the 0.60 cut - the nearest non-public chunk is simply too
far - so they take `probe_access`'s earliest exit into the lexical arm, a branch the
table could not see. On one of them (`probe-public-025`, nearest chunk at distance
0.7251) the keyword arm names `parent` for a question a **public** document answers, a
false hint the table recorded as a correct silence.

So this file asserts two things a future refactor must not undo:

  - the harness's `shipped` column really routes through `probe_access`;
  - the transcription still diverges from it exactly where it is known to, so that
    *new* drift fails loudly instead of being discovered by a live probe two sessions
    later.

The script is loaded from its path rather than imported as a module, because `scripts/`
is not a package - the same reason its sibling reads source with `ast`.
"""

import asyncio
import importlib.util
from pathlib import Path
from typing import Any

import pytest
from intellichoice_db.repositories.rag import ChunkFilters
from intellichoice_shared.access_probe_policy import AudienceMatch

_SCRIPT = (
    Path(__file__).resolve().parents[3] / "scripts" / "measure_access_probe_rules.py"
)


def _harness() -> Any:
    spec = importlib.util.spec_from_file_location("_probe_rule_harness", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def harness() -> Any:
    return _harness()


class _LexicalRepo:
    """A repo whose only behaviour is the keyword arm, which is the arm the harness's
    rules never modelled. `matches` is what `count_matching_by_audience` returns.
    """

    def __init__(self, matches: dict[str, AudienceMatch] | None = None) -> None:
        self.matches = matches or {}
        self.lexical_calls = 0

    async def count_matching_by_audience(
        self, filters: Any, query: str, query_embedding: Any = None, **kwargs: Any
    ) -> dict[str, AudienceMatch]:
        del filters, query, query_embedding, kwargs
        self.lexical_calls += 1
        return dict(self.matches)


def _row(harness: Any, candidates: list[tuple[str, float, float]], case_id: str) -> Any:
    """One `_Row` from `(audience, distance, rerank_score)` triples."""
    return harness._Row(
        case={
            "id": case_id,
            "category": "public",
            "query": "how do I get or delete my kid's records",
            "expected_required_role": None,
            "source_chunk_id": None,
        },
        n_lex=0,
        kw_legacy=[],
        kw_ranked=[],
        semantic=[
            harness._Candidate(
                chunk_id=f"c{i}",
                audience=audience,
                document_id="d",
                text="passage",
                distance=distance,
            )
            for i, (audience, distance, _) in enumerate(candidates)
        ],
        accessible=None,
        src=None,
        rerank={f"c{i}": score for i, (_, _, score) in enumerate(candidates)},
    )


def test_the_shipped_column_calls_probe_access_rather_than_restating_it(
    harness: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The fix itself. If someone re-transcribes the rule into this file, the `shipped`
    column stops being evidence about production, which is AUD-C-25 exactly.
    """
    called: list[str] = []

    async def _spy(*args: Any, **kwargs: Any) -> Any:
        called.append(kwargs["query"])
        raise AssertionError("stop here - reaching this proves the call is made")

    monkeypatch.setattr(harness, "probe_access", _spy)
    row = _row(harness, [("parent", 0.30, 0.95)], "probe-spy")

    with pytest.raises(AssertionError):
        asyncio.run(harness._shipped_hint(row, row.rerank, _LexicalRepo()))

    assert called == ["how do I get or delete my kid's records"]


def test_an_empty_candidate_pool_reaches_the_lexical_arm_and_the_transcription_cannot(
    harness: Any,
) -> None:
    """AUD-C-25's costly half, as a regression test.

    Every candidate sits beyond the 0.60 cut, so `probe_access` returns *before* any model
    call and asks the keyword arm. The transcription returns silence. The measured instance
    is `probe-public-025`: nearest non-public chunk at 0.7251, keyword arm naming `parent`
    for a question a public document answers.
    """
    row = _row(harness, [("branch_manager", 0.7251, 0.10), ("parent", 0.7617, 0.10)], "empty-pool")
    repo = _LexicalRepo({"parent": AudienceMatch(count=1, score=None)})

    shipped = asyncio.run(harness._shipped_hint(row, row.rerank, repo))
    transcription = harness.rerank_prefloor_margin_hint(row, 0.9, 0.10, cut=0.60)

    assert repo.lexical_calls == 1, "probe_access must consult the keyword arm here"
    assert shipped is not None and shipped.required_role == "parent"
    assert transcription is None, (
        "the transcription scores this branch as a silence - the divergence AUD-C-25 is about"
    )


def test_a_sub_floor_winner_also_reaches_the_lexical_arm(harness: Any) -> None:
    """The other divergence, and the one AUD-C-25 was first written up as. The winner
    clears the tier margin but fails the 0.9 floor, so production asks the keyword arm
    while the transcription returns silence without asking.
    """
    row = _row(harness, [("branch_manager", 0.30, 0.90), ("parent", 0.35, 0.30)], "sub-floor")
    repo = _LexicalRepo()

    shipped = asyncio.run(harness._shipped_hint(row, row.rerank, repo))
    transcription = harness.rerank_prefloor_margin_hint(row, 0.9, 0.10, cut=0.60)

    assert repo.lexical_calls == 1
    # This keyword arm has nothing, so both end at silence - by different routes, which is
    # why the outcome agreeing here is not evidence that the rules agree.
    assert shipped is None
    assert transcription is None


def test_two_audiences_inside_the_margin_skip_the_lexical_arm(harness: Any) -> None:
    """The pre-floor margin *gates* the keyword arm: with the top two bests within 0.10 of
    each other, `probe_access` returns an empty match set without consulting it. Recorded
    because `_lexical_only`'s own docstring calls the arm "strictly additive", which this
    branch makes untrue.
    """
    row = _row(harness, [("branch_manager", 0.30, 0.0), ("parent", 0.35, 0.0)], "margin-tie")
    repo = _LexicalRepo({"parent": AudienceMatch(count=1, score=None)})

    shipped = asyncio.run(harness._shipped_hint(row, row.rerank, repo))

    assert repo.lexical_calls == 0, "the margin returns before the keyword arm is asked"
    assert shipped is None


def test_a_clear_winner_above_the_floor_needs_no_fallback(harness: Any) -> None:
    """The happy path, so the tests above are read as branch coverage rather than as a
    claim that the probe never names a tier.
    """
    row = _row(harness, [("parent", 0.30, 0.95), ("branch_manager", 0.35, 0.20)], "clear")
    repo = _LexicalRepo()

    shipped = asyncio.run(harness._shipped_hint(row, row.rerank, repo))

    assert repo.lexical_calls == 0
    assert shipped is not None and shipped.required_role == "parent"


def test_the_replay_gateway_is_free_and_offline(harness: Any) -> None:
    """The replay must not be able to spend money: `--load` exists so that rules are
    compared against identical model output, and a gateway that silently called Bedrock
    would break both that and the cost claim.
    """
    candidates = [harness._ReplayChunk(chunk_id="c0", audience="parent", chunk_text="t")]
    gateway = harness._ReplayGateway({"c0": 0.95}, candidates)

    result = asyncio.run(
        gateway.generate_structured(
            task=None,
            system_prompt="",
            payload=ChunkFilters(),
            response_model=dict,
            max_output_tokens=0,
            session_spend_cents=0.0,
        )
    )

    assert result.cost_cents == 0.0
    assert result.model_id == "replay"
    assert [(s.candidate_index, s.relevance_score) for s in result.value.scores] == [(0, 0.95)]


def test_a_replay_without_a_database_fails_loudly_instead_of_scoring_a_silence(
    harness: Any,
) -> None:
    """The one thing this fix must not do is reintroduce its own defect. If the lexical
    arm cannot be reached, that has to be an error - returning `{}` would score the
    unmodelled branch as a silence, which is what the finding is.
    """
    row = _row(harness, [("parent", 0.90, 0.10)], "no-db")

    with pytest.raises(RuntimeError, match="no database session"):
        asyncio.run(harness._shipped_hint(row, row.rerank, None))
