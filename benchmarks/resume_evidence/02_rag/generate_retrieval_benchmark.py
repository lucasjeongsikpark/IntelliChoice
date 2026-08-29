"""E2.1: build `retrieval_benchmark.yaml` - chunk-level ground truth for E2.2's ablation.

    eval "$(aws configure export-credentials --profile jeongsik-staging-admin --format env)" && \
    AWS_REGION=us-east-1 uv run python \
      benchmarks/resume_evidence/02_rag/generate_retrieval_benchmark.py \
      --out apps/chat-api/tests/fixtures/retrieval_benchmark.yaml --budget-cents 90

**Why a new fixture at all.** Theme 2's recorded weakness is that the only ground truth in
this repository is *document*-level over three documents, so nothing here can distinguish
"retrieval put the right document third" from "retrieval put the right passage third". This
file produces one ground truth per groundable approved chunk, so Recall@k means what the
name says.

**The four controls carried over from `scripts/generate_probe_eval_fixture.py`**, because
each one exists to stop this fixture from measuring itself:

1. *Blind rewrite.* The `paraphrase` phrasing is written by a pass that sees the seed
   question and never the passage, so it cannot echo the document by construction rather
   than by instruction (AUD-C-21).
2. *Measured lexical overlap.* Every phrasing records the fraction of its content words
   that also appear in its source chunk. Overlap is measured with the same `_lexemes`
   stemmer the probe generator uses - `test_e2_retrieval_benchmark_fixture.py` loads both
   and asserts they agree, so the two fixtures' overlap columns stay comparable.
3. *Answerability check.* Every rewritten phrasing is re-checked against its own passage
   and DROPPED if it drifted into a different question. A drifted phrasing is not a harder
   query, it is a query whose ground truth is wrong, and a wrong ground truth flatters
   every arm that fails to find it.
4. *Measurement beats intent.* A phrasing generated under the `lexical_mismatch`
   instruction whose measured overlap comes out above `--mismatch-max-overlap` is
   **relabelled** to `paraphrase` and records `relabelled_from`. The category a case is
   reported under is the one its numbers support, never the one its prompt asked for.

**Groundability floor.** `--min-chunk-chars 100` is not a round number chosen for comfort:
the corpus has no chunk of length in [80, 100), so 100 sits in a natural gap, and it admits
123 of the 144 approved+effective chunks. The 21 it excludes are headings and stubs
("## Branch Managers", 18 chars) that no question can be grounded in - the Frozen Spec's
"5 approved chunks under 20 chars (ungroundable)" case, widened by measurement.

**No-answer controls are validated, not asserted.** A control that some chunk actually
answers is a false negative dressed as a hard case. Each candidate is embedded with real
Titan, its `--na-neighbours` nearest approved chunks are pulled, and the answerability
judge is asked about each one; a candidate any neighbour answers is dropped with its
reason recorded. That check is deliberately *not* the retrieval threshold this benchmark
is measuring - using the instrument under test to validate its own negative set is the
circularity that would make the no-answer table meaningless.

**Writes nothing.** The corpus re-embed needed by the no-answer validation happens inside a
transaction that is always rolled back, so the dev database keeps its mock vectors
(`knowledge-content/` and `rag_chunks` are both left byte-identical). Cost is bounded by
`--budget-cents`, checked after every call, aborting rather than truncating.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import random
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import yaml
from intellichoice_db.engine import create_engine
from intellichoice_shared.bedrock import BedrockTask
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_MAX_OUTPUT_TOKENS = 300

# ---------------------------------------------------------------------------------------
# Prompts. Pass A sees the passage; pass B never does; passes C and D see it in order to
# work *against* it (C must know which words to avoid, D must know which facts to combine).
# ---------------------------------------------------------------------------------------

_SEED_PROMPT = (
    "You write evaluation questions for a school organization's help assistant.\n"
    "Given one passage from an internal document, write the ONE question a real person "
    "would type that this passage answers.\n\n"
    "Hard rules:\n"
    "1. The passage must genuinely answer your question. Do not ask something it only "
    "hints at.\n"
    "2. Ask about the specific thing THIS passage says, not the general topic. If the "
    "passage is one person's biography, name that person.\n"
    "3. Write it as one natural question, at most 20 words. No preamble, no quotes.\n"
    "4. Never mention that you were shown a passage."
)

# AUD-C-21's prompt verbatim in spirit: no passage in the input, so the rewrite cannot
# borrow the document's vocabulary even if it wants to. `asked_by` is one metadata word and
# is here because without it the rewriter silently reassigns the speaker (a tutor's question
# about a student becomes a parent's question about their child), which the answerability
# judge then correctly throws out - losing every non-parent case.
_PARAPHRASE_PROMPT = (
    "You rewrite questions the way an ordinary person would actually type them into a "
    "school's help chat.\n\n"
    "You will be given one question written by staff, and who is asking it. Rewrite it in "
    "that person's own everyday words, as someone who has never read any internal document.\n\n"
    "Hard rules:\n"
    "1. Keep the information need EXACTLY the same. Someone who answers your version must "
    "have answered the original.\n"
    "2. Do NOT change who is asking or whose situation it is.\n"
    "3. Use everyday words. Replace institutional or policy vocabulary with what a person "
    "would say instead.\n"
    "4. Write it the way people really type: direct, sometimes slightly vague, at most 25 "
    "words. One question only.\n"
    "5. Do not add details that were not in the original question.\n"
    "6. Keep any personal name that appears in the original question exactly as written."
)

_MISMATCH_PROMPT = (
    "You write the HARDEST possible search query for a passage: same meaning, no shared "
    "words.\n\n"
    "You are given a passage and a question it answers. Rewrite the question so that it "
    "still has the same answer, but shares as few words as possible with the passage.\n\n"
    "Hard rules:\n"
    "1. Someone reading ONLY that passage must still be able to answer your question "
    "completely. Same information need, different words.\n"
    "2. Use synonyms, everyday paraphrase and different sentence shape. Avoid every "
    "distinctive noun, verb and adjective the passage uses.\n"
    "3. A personal name is the ONE exception: if the question is about a named person, keep "
    "the name, because removing it changes which passage answers the question.\n"
    "4. One natural question, at most 25 words. No preamble, no quotes."
)

_MULTI_KEYWORD_PROMPT = (
    "You write evaluation questions that require combining several facts.\n\n"
    "Given one passage, write ONE question that can only be answered by using at least TWO "
    "different specific details from it - for example a condition AND a deadline, or a role "
    "AND a procedure.\n\n"
    "Hard rules:\n"
    "1. Both details must be in THIS passage. Do not require anything it does not say.\n"
    "2. The question must read like something a real person would type, not like a quiz.\n"
    "3. One question, at most 30 words. No preamble, no quotes."
)

_ANSWERABLE_PROMPT = (
    "You check whether a passage answers a question.\n\n"
    "Answer true only if someone who read ONLY this passage could give a substantially "
    "complete answer to the question. Answer false if the passage merely mentions the "
    "topic, covers a different case, or answers a related but different question."
)


class _ChunkPayload(BaseModel):
    passage: str
    audience: str


class _QuestionPayload(BaseModel):
    question: str
    asked_by: str


class _PassageQuestionPayload(BaseModel):
    passage: str
    question: str


class _AnswerabilityPayload(BaseModel):
    passage: str
    question: str


class _GeneratedQuestion(BaseModel):
    question: str = Field(min_length=8, max_length=300)


class _Answerability(BaseModel):
    answerable: bool
    # No max_length: a model cannot count characters, and bounding a free-text field turns a
    # good judgement into a StructuredOutputError after the repair retry - that mistake cost
    # the probe generator 19 of 55 cases and recorded them as evidence about the cases.
    reason: str


# ---------------------------------------------------------------------------------------
# Lexical overlap. Byte-identical to `scripts/generate_probe_eval_fixture.py::_lexemes` so
# the `lexical_overlap` column here means the same thing as the one in `probe_eval.yaml`;
# `test_e2_retrieval_benchmark_fixture.py` loads both and asserts they agree on literals.
# ---------------------------------------------------------------------------------------

_STOPWORDS = {
    "the", "and", "for", "are", "you", "your", "with", "that", "this", "from", "can", "not",
    "any", "all", "has", "have", "was", "were", "will", "who", "how", "what", "when", "does",
    "did", "why", "our", "out", "get", "one", "own", "they", "their", "there", "them", "than",
    "then", "into", "each", "some", "may", "must", "should",
}  # fmt: skip


def lexemes(sql_text: str) -> set[str]:
    words = re.findall(r"[a-z]{3,}", sql_text.lower())
    return {w[:-1] if w.endswith("s") and len(w) > 4 else w for w in words if w not in _STOPWORDS}


def overlap(question: str, passage: str) -> float:
    q_lex, c_lex = lexemes(question), lexemes(passage)
    return round(len(q_lex & c_lex) / len(q_lex), 3) if q_lex else 0.0


def overlap_band(value: float) -> str:
    """The measured band, reported beside the generator's intent so a reader can check that
    the intent held. Thresholds are descriptive labels for the report's overlap column, not
    gates - the only gate is `--mismatch-max-overlap` on the `lexical_mismatch` pass.
    """
    if value >= 0.50:
        return "high"
    return "mid" if value >= 0.15 else "low"


_ASKED_BY = {
    "parent": "a parent of a student",
    "student": "a student",
    "tutor": "a tutor who works here",
    "branch_manager": "a branch manager who works here",
    "public": "someone visiting the website",
}


@dataclass
class Chunk:
    chunk_id: str
    document_id: str
    document_title: str
    section_title: str | None
    audience: str
    branch_external_id: str | None
    chunk_text: str

    @property
    def stratum(self) -> str:
        """Three strata, and they are corpus facts rather than a taxonomy invented here.

        `near_duplicate_cluster` - `public/our-team`'s staff biographies, ~36 groundable
        chunks with near-identical shape ("### Name  *Role*  Dr. Name is a ..."), which is
        where single-chunk ground truth is genuinely hard and where a lexical arm should
        struggle most.
        `authorization_boundary` - a chunk no anonymous caller may retrieve; scored under the
        audience filter a caller holding that role would actually get (SPEC §5.21.3).
        `general` - the rest of the public corpus.
        """
        if self.document_id == "public-our-team":
            return "near_duplicate_cluster"
        return "general" if self.audience == "public" else "authorization_boundary"


class Spend:
    def __init__(self, ceiling_cents: float) -> None:
        self.ceiling_cents = ceiling_cents
        self.total_cents = 0.0
        self.calls = 0

    def add(self, amount: float) -> None:
        self.total_cents += amount
        self.calls += 1
        if self.total_cents > self.ceiling_cents:
            raise SystemExit(
                f"budget of {self.ceiling_cents} cents exceeded ({self.total_cents:.2f}) "
                "- aborting rather than writing a partial fixture"
            )


@dataclass
class _Drop:
    case_id: str
    phrasing: str
    reason: str


@dataclass
class _Run:
    spend: Spend
    drops: list[_Drop] = field(default_factory=list)
    failures: list[_Drop] = field(default_factory=list)


def _gateway(region: str, model: str, per_call_budget_cents: float):
    from intellichoice_adapters.bedrock.bedrock_runtime_provider import AnthropicBedrockProvider
    from intellichoice_adapters.bedrock.gateway import ResilientBedrockGateway
    from intellichoice_adapters.bedrock.titan_embedding_provider import TitanEmbeddingProvider

    return ResilientBedrockGateway(
        provider=AnthropicBedrockProvider(aws_region=region),
        embedding_provider=TitanEmbeddingProvider(aws_region=region),
        model_registry={
            BedrockTask.SCOPE_AND_INTENT: model,
            BedrockTask.EMBEDDING: "amazon.titan-embed-text-v2:0",
        },
        session_budget_cents=per_call_budget_cents,
    )


async def _generate(gateway, run: _Run, prompt: str, payload: BaseModel) -> str:
    result = await gateway.generate_structured(
        task=BedrockTask.SCOPE_AND_INTENT,
        system_prompt=prompt,
        payload=payload,
        response_model=_GeneratedQuestion,
        max_output_tokens=_MAX_OUTPUT_TOKENS,
        session_spend_cents=0.0,
    )
    run.spend.add(result.cost_cents)
    return result.value.question.strip()


async def _answerable(gateway, run: _Run, passage: str, question: str) -> tuple[bool, str]:
    result = await gateway.generate_structured(
        task=BedrockTask.SCOPE_AND_INTENT,
        system_prompt=_ANSWERABLE_PROMPT,
        payload=_AnswerabilityPayload(passage=passage, question=question),
        response_model=_Answerability,
        max_output_tokens=_MAX_OUTPUT_TOKENS,
        session_spend_cents=0.0,
    )
    run.spend.add(result.cost_cents)
    return result.value.answerable, result.value.reason[:300]


async def _load_chunks(session: AsyncSession, min_chars: int) -> list[Chunk]:
    rows = (
        await session.execute(
            text(
                """
                SELECT c.chunk_id, c.document_id, d.title AS document_title, c.section_title,
                       c.audience, c.branch_external_id, c.chunk_text
                FROM rag_chunks c JOIN rag_documents d ON d.document_id = c.document_id
                WHERE c.status = 'approved'
                  AND c.effective_from <= now()
                  AND (c.effective_to IS NULL OR c.effective_to > now())
                  AND length(c.chunk_text) >= :min_len
                ORDER BY c.document_id, c.chunk_id
                """
            ),
            {"min_len": min_chars},
        )
    ).all()
    return [
        Chunk(
            chunk_id=str(r.chunk_id),
            document_id=r.document_id,
            document_title=r.document_title,
            section_title=r.section_title,
            audience=r.audience,
            branch_external_id=r.branch_external_id,
            chunk_text=r.chunk_text,
        )
        for r in rows
    ]


def _reused_phrasings(chunk: Chunk, probe_cases: dict[str, dict]) -> list[dict[str, Any]]:
    """`probe_eval.yaml`'s two phrasings for a chunk, carried over free of charge.

    They were produced by exactly the two passes this generator runs first - a
    passage-derived seed (`query`) and a blind rewrite that never saw the passage
    (`human_query`, answerability-checked at generation time) - so reusing them costs
    nothing and keeps 50 of the 123 ground truths comparable with the earlier instrument.
    Overlap is re-measured here rather than copied, because the stored value was measured
    against whatever the chunk text was then.
    """
    case = probe_cases.get(chunk.chunk_id)
    if case is None:
        return []
    phrasings: list[dict[str, Any]] = []
    for field_name, phrasing, pass_id in (
        ("query", "exact_lookup", "A"),
        ("human_query", "paraphrase", "B"),
    ):
        value = (case.get(field_name) or "").strip()
        if not value:
            continue
        measured = overlap(value, chunk.chunk_text)
        phrasings.append(
            {
                "phrasing": phrasing,
                "text": value,
                "lexical_overlap": measured,
                "overlap_band": overlap_band(measured),
                "generator_pass": pass_id,
                "reused_from": f"probe_eval.yaml#{case['id']}",
                "answerability_checked": field_name == "human_query",
            }
        )
    return phrasings


async def _build_ground_truths(
    *,
    gateway,
    run: _Run,
    chunks: list[Chunk],
    probe_cases: dict[str, dict],
    mismatch_ids: set[str],
    multi_ids: set[str],
    mismatch_max_overlap: float,
) -> list[dict[str, Any]]:
    ground_truths: list[dict[str, Any]] = []
    for index, chunk in enumerate(chunks):
        case_id = f"gt-{chunk.stratum[:4]}-{index:03d}"
        asked_by = _ASKED_BY.get(chunk.audience, _ASKED_BY["public"])
        phrasings = _reused_phrasings(chunk, probe_cases)

        if not phrasings:
            try:
                seed = await _generate(
                    gateway,
                    run,
                    _SEED_PROMPT,
                    _ChunkPayload(passage=chunk.chunk_text, audience=chunk.audience),
                )
            except Exception as exc:  # a failed call is not evidence about the chunk
                run.failures.append(_Drop(case_id, "exact_lookup", f"{type(exc).__name__}: {exc}"))
                print(f"  FAIL {case_id} seed {type(exc).__name__}", file=sys.stderr)
                continue
            measured = overlap(seed, chunk.chunk_text)
            phrasings.append(
                {
                    "phrasing": "exact_lookup",
                    "text": seed,
                    "lexical_overlap": measured,
                    "overlap_band": overlap_band(measured),
                    "generator_pass": "A",
                    "reused_from": None,
                    "answerability_checked": False,
                }
            )
            try:
                rewrite = await _generate(
                    gateway,
                    run,
                    _PARAPHRASE_PROMPT,
                    _QuestionPayload(question=seed, asked_by=asked_by),
                )
                ok, reason = await _answerable(gateway, run, chunk.chunk_text, rewrite)
            except Exception as exc:
                run.failures.append(_Drop(case_id, "paraphrase", f"{type(exc).__name__}: {exc}"))
                ok, rewrite, reason = False, "", "call failed"
            if ok and rewrite:
                measured = overlap(rewrite, chunk.chunk_text)
                phrasings.append(
                    {
                        "phrasing": "paraphrase",
                        "text": rewrite,
                        "lexical_overlap": measured,
                        "overlap_band": overlap_band(measured),
                        "generator_pass": "B",
                        "reused_from": None,
                        "answerability_checked": True,
                    }
                )
            elif rewrite:
                run.drops.append(_Drop(case_id, "paraphrase", f"rewrite drifted: {reason}"))

        seed_text = phrasings[0]["text"] if phrasings else ""
        if chunk.chunk_id in mismatch_ids and seed_text:
            try:
                hard = await _generate(
                    gateway,
                    run,
                    _MISMATCH_PROMPT,
                    _PassageQuestionPayload(passage=chunk.chunk_text, question=seed_text),
                )
                ok, reason = await _answerable(gateway, run, chunk.chunk_text, hard)
            except Exception as exc:
                run.failures.append(
                    _Drop(case_id, "lexical_mismatch", f"{type(exc).__name__}: {exc}")
                )
                ok, hard, reason = False, "", "call failed"
            if ok and hard:
                measured = overlap(hard, chunk.chunk_text)
                # Control 4: measurement beats intent. An overlap above the ceiling means
                # this is a paraphrase, whatever the prompt asked for, and reporting it in
                # the lexical_mismatch row would inflate that row's difficulty claim.
                relabelled = measured > mismatch_max_overlap
                phrasings.append(
                    {
                        "phrasing": "paraphrase" if relabelled else "lexical_mismatch",
                        "text": hard,
                        "lexical_overlap": measured,
                        "overlap_band": overlap_band(measured),
                        "generator_pass": "C",
                        "reused_from": None,
                        "answerability_checked": True,
                        **({"relabelled_from": "lexical_mismatch"} if relabelled else {}),
                    }
                )
            elif hard:
                run.drops.append(_Drop(case_id, "lexical_mismatch", f"rewrite drifted: {reason}"))

        if chunk.chunk_id in multi_ids:
            try:
                multi = await _generate(
                    gateway,
                    run,
                    _MULTI_KEYWORD_PROMPT,
                    _ChunkPayload(passage=chunk.chunk_text, audience=chunk.audience),
                )
                ok, reason = await _answerable(gateway, run, chunk.chunk_text, multi)
            except Exception as exc:
                run.failures.append(_Drop(case_id, "multi_keyword", f"{type(exc).__name__}: {exc}"))
                ok, multi, reason = False, "", "call failed"
            if ok and multi:
                measured = overlap(multi, chunk.chunk_text)
                phrasings.append(
                    {
                        "phrasing": "multi_keyword",
                        "text": multi,
                        "lexical_overlap": measured,
                        "overlap_band": overlap_band(measured),
                        "generator_pass": "D",
                        "reused_from": None,
                        "answerability_checked": True,
                    }
                )
            elif multi:
                run.drops.append(_Drop(case_id, "multi_keyword", f"question drifted: {reason}"))

        if not phrasings:
            continue
        for position, phrasing in enumerate(phrasings):
            phrasing["id"] = f"{case_id}-q{position}"
        ground_truths.append(
            {
                "id": case_id,
                "stratum": chunk.stratum,
                "audience": chunk.audience,
                "branch_external_id": chunk.branch_external_id,
                "source_document_id": chunk.document_id,
                "source_document_title": chunk.document_title,
                "source_section_title": chunk.section_title,
                # A LIST, not a scalar: the Frozen Spec allows a set ground truth for the
                # bio cluster and `ir_metrics` scores sets. Every entry here happens to be a
                # singleton (each bio names its own person, so the answer is one passage) -
                # `cluster_size` records the near-duplicate neighbourhood it sits in, which
                # is what makes the near_duplicate_cluster row's difficulty legible.
                "chunk_ids": [chunk.chunk_id],
                "cluster_size": 1,
                "source_chars": len(chunk.chunk_text),
                "reused_from": phrasings[0].get("reused_from"),
                "queries": phrasings,
            }
        )
        print(
            f"  {case_id:<20} {chunk.stratum:<22} {len(phrasings)} phrasings  "
            f"{run.spend.total_cents:.2f}c",
            file=sys.stderr,
        )
    return ground_truths


# In-scope questions a real person could ask that NO chunk in this corpus answers. The eight
# `no-answer-*` ids are carried over verbatim from `qa_coverage_eval.yaml`, where they have
# been scored on the real lane since S37; the ten `na-e2-*` ids are new, written to the same
# shape (plausible, specific, about this organization, unanswered by the corpus). Every one
# of them is validated below against its real-Titan nearest neighbours before it is written.
# The eight `no-answer-*` ids are carried over verbatim from `qa_coverage_eval.yaml`; the ten
# `na-e2-*` ids are new, written to the same shape. `_reused_control_source` records which is
# which, so the report can say how much of the negative set is new rather than inherited.
_NO_ANSWER_CANDIDATES: list[tuple[str, str]] = [
    ("no-answer-cost-1", "How much does the SAT Prep Camp cost for a returning student?"),
    ("no-answer-ratio-1", "What is the student-to-tutor ratio in a typical session?"),
    ("no-answer-sitin-1", "Can a parent sit in and watch the whole tutoring session?"),
    ("no-answer-transport-1", "Does IntelliChoice provide transportation for students?"),
    ("no-answer-missed-1", "What happens to a student who misses three sessions in a row?"),
    ("no-answer-supplies-1", "Do students need to bring their own laptop to a session?"),
    ("no-answer-language-1", "Are tutoring sessions available in Spanish for parents?"),
    ("no-answer-agecap-1", "Is there an age limit for a student to keep attending?"),
    ("na-e2-refund-1", "How do I get a refund if we signed up and then changed our minds?"),
    ("na-e2-scholarship-1", "Is there financial aid for families who cannot pay the fee?"),
    ("na-e2-snack-1", "Are snacks or lunch provided during the longer weekend sessions?"),
    ("na-e2-parking-1", "Where do parents park when they drop their child off at a branch?"),
    ("na-e2-insurance-1", "Does the program carry accident insurance for students on site?"),
    ("na-e2-summer-1", "What are the dates of the summer break camp this year?"),
    ("na-e2-sibling-1", "Is there a sibling discount if I enroll two children at once?"),
    ("na-e2-college-1", "Do you write college recommendation letters for students?"),
    ("na-e2-waitlist-1", "How long is the waitlist if a branch is already full this term?"),
    ("na-e2-device-1", "What happens if a student breaks a tablet that belongs to a branch?"),
]


def _reused_control_source(control_id: str) -> str | None:
    """The eight `no-answer-*` prefixed ids exist in `qa_coverage_eval.yaml`; `na-e2-*` are new."""
    return f"qa_coverage_eval.yaml#{control_id}" if control_id.startswith("no-answer-") else None


async def _validate_no_answer(
    *, session: AsyncSession, gateway, run: _Run, neighbours: int
) -> tuple[list[dict[str, Any]], list[_Drop]]:
    """Drop any candidate that a nearby approved chunk actually answers.

    Real Titan embeddings on both sides (the corpus was re-embedded by the caller inside its
    rolled-back transaction), nearest `neighbours` chunks by cosine distance over the whole
    approved+effective corpus - every audience, not just public, because a control that the
    *parent* handbook answers is not a no-answer case for a parent.
    """
    kept: list[dict[str, Any]] = []
    dropped: list[_Drop] = []
    for control_id, question in _NO_ANSWER_CANDIDATES:
        embedding = await gateway.create_embedding(texts=[question], session_spend_cents=0.0)
        run.spend.add(embedding.cost_cents)
        rows = (
            await session.execute(
                text(
                    """
                    SELECT chunk_id, document_id, chunk_text,
                           embedding <=> CAST(:q AS vector) AS distance
                    FROM rag_chunks
                    WHERE status = 'approved'
                      AND effective_from <= now()
                      AND (effective_to IS NULL OR effective_to > now())
                      AND embedding IS NOT NULL
                    ORDER BY distance
                    LIMIT :n
                    """
                ),
                {"q": str(embedding.vectors[0]), "n": neighbours},
            )
        ).all()
        judged: list[dict[str, Any]] = []
        answered_by: str | None = None
        for row in rows:
            ok, reason = await _answerable(gateway, run, row.chunk_text, question)
            judged.append(
                {
                    "chunk_id": str(row.chunk_id),
                    "document_id": row.document_id,
                    "distance": round(float(row.distance), 4),
                    "answerable": ok,
                }
            )
            if ok:
                answered_by = f"{row.document_id}/{str(row.chunk_id)[:8]}: {reason}"
                break
        if answered_by:
            dropped.append(
                _Drop(control_id, "no_answer", f"a corpus chunk answers it - {answered_by}")
            )
            print(f"  DROP {control_id}: {answered_by[:110]}", file=sys.stderr)
            continue
        kept.append(
            {
                "id": control_id,
                "text": question,
                "reused_from": _reused_control_source(control_id),
                "validated_neighbours": judged,
            }
        )
        print(f"  {control_id:<24} {len(judged)} neighbours judged unanswerable", file=sys.stderr)
    return kept, dropped


def _repo_sha() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except Exception:
        return "unknown"


async def _run(args: argparse.Namespace) -> int:
    probe_raw = yaml.safe_load(open(args.probe_fixture, encoding="utf-8"))
    probe_cases = {
        str(c["source_chunk_id"]): c for c in probe_raw["cases"] if c.get("source_chunk_id")
    }
    # Built only for a paid run: constructing the boto3 client resolves credentials, and
    # `--dry-run` must stay runnable with no AWS session at all (D-164).
    gateway = (
        None if args.dry_run else _gateway(args.region, args.model, args.per_call_budget_cents)
    )
    run = _Run(spend=Spend(args.budget_cents))
    engine = create_engine()
    payload: dict[str, Any] = {}
    try:
        async with engine.connect() as conn:
            trans = await conn.begin()
            session = AsyncSession(bind=conn, join_transaction_mode="create_savepoint")
            chunks = await _load_chunks(session, args.min_chunk_chars)
            print(
                f"{len(chunks)} groundable chunks (>= {args.min_chunk_chars} chars); "
                f"{sum(1 for c in chunks if c.chunk_id in probe_cases)} reuse probe_eval",
                file=sys.stderr,
            )

            # Deterministic, stratified sampling of which ground truths get the two extra
            # phrasing passes - seeded so a re-run selects the same cases, and stratified so
            # neither extra category is accidentally all-public or all-bio.
            rng = random.Random(args.seed)
            mismatch_ids: set[str] = set()
            multi_ids: set[str] = set()
            by_stratum: dict[str, list[Chunk]] = {}
            for chunk in chunks:
                by_stratum.setdefault(chunk.stratum, []).append(chunk)
            for _stratum, group in sorted(by_stratum.items()):
                share = max(1, round(args.mismatch_cases * len(group) / len(chunks)))
                mismatch_ids |= {c.chunk_id for c in rng.sample(group, min(share, len(group)))}
                eligible = [c for c in group if len(c.chunk_text) >= args.multi_keyword_min_chars]
                share = max(1, round(args.multi_keyword_cases * len(group) / len(chunks)))
                multi_ids |= {c.chunk_id for c in rng.sample(eligible, min(share, len(eligible)))}
            print(
                f"extra passes: {len(mismatch_ids)} lexical_mismatch, {len(multi_ids)} "
                f"multi_keyword (seed {args.seed})",
                file=sys.stderr,
            )

            if args.dry_run:
                # Free preflight, the shape `make question-gen-preflight` established: says
                # exactly what a paid run would generate, calls nothing and writes nothing.
                planned = (
                    sum(2 if c.chunk_id not in probe_cases else 2 for c in chunks)
                    + len(mismatch_ids)
                    + len(multi_ids)
                )
                by_stratum_counts = {k: len(v) for k, v in sorted(by_stratum.items())}
                print(
                    f"DRY RUN - no model call made.\n"
                    f"  ground truths: {len(chunks)} {by_stratum_counts}\n"
                    f"  query instances (upper bound, before drift drops): {planned}\n"
                    f"  reused free from probe_eval: "
                    f"{sum(1 for c in chunks if c.chunk_id in probe_cases) * 2}\n"
                    f"  no-answer controls to validate: {len(_NO_ANSWER_CANDIDATES)}",
                    file=sys.stderr,
                )
                await session.close()
                await trans.rollback()
                return 0

            ground_truths = await _build_ground_truths(
                gateway=gateway,
                run=run,
                chunks=chunks,
                probe_cases=probe_cases,
                mismatch_ids=mismatch_ids,
                multi_ids=multi_ids,
                mismatch_max_overlap=args.mismatch_max_overlap,
            )

            print("\nvalidating no-answer controls against real-Titan neighbours:", file=sys.stderr)
            n_reembedded = await _reembed(session, gateway, run)
            controls, control_drops = await _validate_no_answer(
                session=session, gateway=gateway, run=run, neighbours=args.na_neighbours
            )
            await session.close()
            await trans.rollback()
    finally:
        await engine.dispose()

    instances = sum(len(gt["queries"]) for gt in ground_truths)
    payload = {
        "generated_by": "benchmarks/resume_evidence/02_rag/generate_retrieval_benchmark.py",
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "repo_sha": _repo_sha(),
        "generator_model": args.model,
        "embedding_model": "amazon.titan-embed-text-v2:0",
        "seed": args.seed,
        "min_chunk_chars": args.min_chunk_chars,
        "mismatch_max_overlap": args.mismatch_max_overlap,
        "spend_cents": round(run.spend.total_cents, 3),
        "model_calls": run.spend.calls,
        "corpus": {
            "groundable_chunks": len(chunks),
            "reembedded_for_validation": n_reembedded,
        },
        "counts": {
            "ground_truths": len(ground_truths),
            "query_instances": instances,
            "no_answer_controls": len(controls),
        },
        "note": (
            "E2.1. One ground truth per groundable approved+effective chunk; `chunk_ids` is a "
            "LIST because ir_metrics scores set ground truth, and every entry here is a "
            "singleton. `lexical_overlap` is the measured fraction of a phrasing's content "
            "words that also appear in its source chunk - a high mean means the fixture is "
            "measuring its own paraphrase. A `paraphrase` phrasing carrying "
            "`relabelled_from: lexical_mismatch` was generated under the mismatch prompt and "
            "moved here by measurement: the category a case is reported under is the one its "
            "numbers support. `no_answer_controls` were each validated against their real-Titan "
            "nearest neighbours by an LLM answerability judge - NOT by the retrieval threshold "
            "this benchmark measures, which would be circular."
        ),
        "ground_truths": ground_truths,
        "no_answer_controls": controls,
        "dropped": [
            {"id": d.case_id, "phrasing": d.phrasing, "reason": d.reason}
            for d in run.drops + control_drops
        ],
        "call_failures": [
            {"id": d.case_id, "phrasing": d.phrasing, "reason": d.reason} for d in run.failures
        ],
    }
    with open(args.out, "w", encoding="utf-8") as fh:
        yaml.safe_dump(payload, fh, sort_keys=False, width=100, allow_unicode=True)

    from collections import Counter

    strata = Counter(gt["stratum"] for gt in ground_truths)
    phrasings = Counter(q["phrasing"] for gt in ground_truths for q in gt["queries"])
    print(
        f"\nwrote {args.out}\n"
        f"  {len(ground_truths)} ground truths {dict(strata)}\n"
        f"  {instances} query instances {dict(phrasings)}\n"
        f"  {len(controls)} no-answer controls kept, {len(control_drops)} dropped\n"
        f"  {len(run.drops)} phrasings dropped for drift, {len(run.failures)} call failures\n"
        f"  spent {run.spend.total_cents:.2f} cents over {run.spend.calls} calls",
        file=sys.stderr,
    )
    return 0


async def _reembed(session: AsyncSession, gateway, run: _Run) -> int:
    """AUD-C-16, and here it serves only the no-answer validation: the local corpus carries
    `MockBedrockProvider` hash vectors, so nearest-neighbour over them would hand the judge
    five random passages and every control would pass validation for the wrong reason.
    Rolled back with the caller's transaction.
    """
    rows = (
        await session.execute(
            text("SELECT chunk_id, chunk_text FROM rag_chunks WHERE status = 'approved'")
        )
    ).all()
    for chunk_id, chunk_text in rows:
        embedding = await gateway.create_embedding(texts=[chunk_text], session_spend_cents=0.0)
        run.spend.add(embedding.cost_cents)
        await session.execute(
            text("UPDATE rag_chunks SET embedding = :e WHERE chunk_id = :c"),
            {"e": str(embedding.vectors[0]), "c": chunk_id},
        )
    await session.flush()
    print(
        f"  re-embedded {len(rows)} approved chunks with real Titan (rolled back)", file=sys.stderr
    )
    return len(rows)


async def _top_up_mismatch(args: argparse.Namespace) -> int:
    """Incremental second pass: add `lexical_mismatch` phrasings to an existing fixture.

    The first full run attempted pass C on 40 ground truths and kept **15**: measurement beats
    intent, so 22 attempts whose measured overlap came out above `--mismatch-max-overlap` were
    relabelled `paraphrase` and 3 drifted and were dropped. A 15-case category cannot carry a
    per-arm row, and the honest way to grow it is *more attempts at the same threshold* - never
    a looser threshold, which would fill the cell by redefining it.

    Deliberately in-place and incremental, the shape `--from-fixture` established: it only
    touches ground truths that have no pass-C phrasing yet, leaves every existing phrasing
    untouched, and appends its own provenance block, so the round-1 numbers stay auditable
    beside the round-2 ones. Relabelled attempts are kept as `paraphrase` here exactly as they
    were in round 1 - discarding round 2's failures while keeping round 1's would make the
    paraphrase cell's composition a function of which run produced it.
    """
    payload = yaml.safe_load(open(args.out, encoding="utf-8"))
    ground_truths: list[dict[str, Any]] = payload["ground_truths"]
    gateway = _gateway(args.region, args.model, args.per_call_budget_cents)
    run = _Run(spend=Spend(args.budget_cents))
    candidates = [
        gt
        for gt in ground_truths
        if not any(q["phrasing"] == "lexical_mismatch" for q in gt["queries"])
        and not any(q.get("relabelled_from") == "lexical_mismatch" for q in gt["queries"])
        and gt["queries"]
    ]
    # Same seed, same stratified shape as round 1, so the top-up is reproducible and does not
    # concentrate on one stratum.
    rng = random.Random(args.seed + 1)
    by_stratum: dict[str, list[dict[str, Any]]] = {}
    for gt in candidates:
        by_stratum.setdefault(gt["stratum"], []).append(gt)
    selected: list[dict[str, Any]] = []
    for _stratum, group in sorted(by_stratum.items()):
        share = max(1, round(args.mismatch_cases * len(group) / max(1, len(candidates))))
        selected.extend(rng.sample(group, min(share, len(group))))
    print(
        f"topping up lexical_mismatch: {len(selected)} attempts over {len(candidates)} "
        f"eligible ground truths (seed {args.seed + 1})",
        file=sys.stderr,
    )

    engine = create_engine()
    kept = relabelled = 0
    try:
        async with engine.connect() as conn:
            trans = await conn.begin()
            session = AsyncSession(bind=conn, join_transaction_mode="create_savepoint")
            chunks = {c.chunk_id: c for c in await _load_chunks(session, args.min_chunk_chars)}
            for gt in selected:
                chunk = chunks.get(gt["chunk_ids"][0])
                if chunk is None:
                    run.drops.append(
                        _Drop(gt["id"], "lexical_mismatch", "chunk no longer approved")
                    )
                    continue
                seed_text = gt["queries"][0]["text"]
                try:
                    hard = await _generate(
                        gateway,
                        run,
                        _MISMATCH_PROMPT,
                        _PassageQuestionPayload(passage=chunk.chunk_text, question=seed_text),
                    )
                    ok, reason = await _answerable(gateway, run, chunk.chunk_text, hard)
                except Exception as exc:
                    run.failures.append(
                        _Drop(gt["id"], "lexical_mismatch", f"{type(exc).__name__}: {exc}")
                    )
                    continue
                if not ok:
                    run.drops.append(
                        _Drop(gt["id"], "lexical_mismatch", f"rewrite drifted: {reason}")
                    )
                    continue
                measured = overlap(hard, chunk.chunk_text)
                is_relabelled = measured > args.mismatch_max_overlap
                gt["queries"].append(
                    {
                        "phrasing": "paraphrase" if is_relabelled else "lexical_mismatch",
                        "text": hard,
                        "lexical_overlap": measured,
                        "overlap_band": overlap_band(measured),
                        "generator_pass": "C2",
                        "reused_from": None,
                        "answerability_checked": True,
                        "id": f"{gt['id']}-q{len(gt['queries'])}",
                        **({"relabelled_from": "lexical_mismatch"} if is_relabelled else {}),
                    }
                )
                relabelled += int(is_relabelled)
                kept += int(not is_relabelled)
            await session.close()
            await trans.rollback()
    finally:
        await engine.dispose()

    instances = sum(len(gt["queries"]) for gt in ground_truths)
    payload["counts"]["query_instances"] = instances
    payload["spend_cents"] = round(payload["spend_cents"] + run.spend.total_cents, 3)
    payload["model_calls"] += run.spend.calls
    payload.setdefault("top_ups", []).append(
        {
            "pass": "C2",
            "at": datetime.now(UTC).isoformat(timespec="seconds"),
            "attempts": len(selected),
            "kept_as_lexical_mismatch": kept,
            "relabelled_to_paraphrase": relabelled,
            "dropped_for_drift": len(run.drops),
            "call_failures": len(run.failures),
            "seed": args.seed + 1,
            "spend_cents": round(run.spend.total_cents, 3),
            "note": (
                "Round 2 of the lexical_mismatch pass, run because round 1 kept only 15 of 40 "
                "attempts under the same `mismatch_max_overlap` gate. More attempts, identical "
                "threshold - the gate was never loosened to fill the cell."
            ),
        }
    )
    payload["dropped"].extend(
        {"id": d.case_id, "phrasing": d.phrasing, "reason": d.reason} for d in run.drops
    )
    payload["call_failures"].extend(
        {"id": d.case_id, "phrasing": d.phrasing, "reason": d.reason} for d in run.failures
    )
    with open(args.out, "w", encoding="utf-8") as fh:
        yaml.safe_dump(payload, fh, sort_keys=False, width=100, allow_unicode=True)
    print(
        f"\ntopped up {args.out}: +{kept} lexical_mismatch, +{relabelled} relabelled to "
        f"paraphrase, {len(run.drops)} dropped for drift | {instances} query instances total "
        f"| spent {run.spend.total_cents:.2f} cents",
        file=sys.stderr,
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="apps/chat-api/tests/fixtures/retrieval_benchmark.yaml")
    parser.add_argument("--probe-fixture", default="apps/chat-api/tests/fixtures/probe_eval.yaml")
    parser.add_argument("--min-chunk-chars", type=int, default=100)
    parser.add_argument("--mismatch-cases", type=int, default=40)
    parser.add_argument("--multi-keyword-cases", type=int, default=40)
    parser.add_argument("--multi-keyword-min-chars", type=int, default=200)
    parser.add_argument("--mismatch-max-overlap", type=float, default=0.15)
    parser.add_argument("--na-neighbours", type=int, default=5)
    parser.add_argument("--seed", type=int, default=20260829)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the generation plan and exit without calling any model or writing.",
    )
    parser.add_argument(
        "--top-up-mismatch",
        action="store_true",
        help="Incremental pass C2: add lexical_mismatch phrasings to --out in place. See "
        "`_top_up_mismatch`.",
    )
    parser.add_argument("--budget-cents", type=float, default=90.0)
    parser.add_argument("--per-call-budget-cents", type=float, default=5.0)
    parser.add_argument("--region", default=os.getenv("AWS_REGION", "us-east-1"))
    parser.add_argument("--model", default="us.anthropic.claude-haiku-4-5-20251001-v1:0")
    args = parser.parse_args()
    if args.top_up_mismatch:
        return asyncio.run(_top_up_mismatch(args))
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
