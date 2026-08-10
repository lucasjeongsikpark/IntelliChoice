"""Dev/test `BedrockProvider` (SPEC §5.25.1) - default provider in dev/tests, mirroring
`FakeEmailTransport`/`FakeTokenIssuer`'s role for their own interfaces (D-002). Produces
plausible, schema-valid JSON without calling any real model, using the same
`BedrockTutorPayload` fields the real provider receives (D-023) so the synthesized
content actually references the student's topic/skill/question.
"""

import hashlib
import json
import random
import re
from collections.abc import Callable
from datetime import datetime

from .provider import RawEmbedding, RawGeneration

# Matches EMBEDDING_DIM in intellichoice_db.models.rag (Titan Text Embeddings V2, D-035).
_MOCK_EMBEDDING_DIM = 1024


def _stable_choice[T](text: str, options: tuple[T, ...]) -> T:
    """Pick one option from `text`, same answer every process (D-238).

    `hash()` is salted per-process by default, so a mock built on it varies run to run -
    the one property a test double must not have. Same reasoning as
    `_deterministic_vector`, which is why both hash rather than trusting `hash()`.
    """
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return options[digest[0] % len(options)]


def _hint_json(payload: dict) -> dict:
    return {
        "hint_text": (
            f"Look again at how {payload.get('skill', 'this skill')} works in "
            f"{payload.get('current_topic', 'this topic')} - what's the first step you "
            "could try?"
        ),
        "concept_reminder": f"Remember the core idea behind {payload.get('skill', 'this skill')}.",
        "next_step_prompt": "What would you try next, given that reminder?",
        "answer_revealed": False,
        "difficulty": 1,
    }


def _hint_personalization_json(payload: dict) -> dict:
    """Deterministic S21 stand-in, distinct from `_hint_json` - varies its text by the
    requested `hint_level`/`misconception_tag` (both real inputs, not invented) so
    default-mock-driven ladder-escalation tests see genuinely different text per level
    without a bespoke scripted gateway, and the "a personalized hint addresses the
    mapped misconception" done-when criterion has something concrete to assert on.

    The level marker is `L{level}`, not `Level {level}`, and that spacing is
    load-bearing - do not "tidy" it back. `tutor.generate_personalized_hint` rejects any
    hint in which `answer_text_leaked` finds the question's correct answer standing
    alone, and a bare `1` in `Level 1` *is* the correct answer for the ~6% of this
    bank's variants whose answer is exactly "1". So the mock's own text made the mock's
    own hint unusable, at a rate set by an unseeded per-request RNG choosing the
    variant - measured at 8 failures in 60 standalone runs of
    `test_hint_reflects_the_students_actual_wrong_option` (S36 continuation; D-097
    recorded this flake as unseeded-RNG-driven, which is the mechanism, but attributed
    it to the fixture rather than to this string). Gluing the digit to a letter puts an
    alphanumeric on one side of it, which is exactly what that check's lookarounds
    require in order not to match.
    """
    level = payload.get("hint_level", 1)
    misconception = payload.get("misconception_tag") or "the general approach"
    skill = payload.get("skill", "this skill")
    canonical = payload.get("canonical_hint_text", "")
    return {
        "hint_text": (
            f"Hint L{level}, addressing {misconception}: {canonical} "
            f"Focus on {skill} and try the next step."
        ),
        "concept_reminder": f"Remember the core idea behind {skill}.",
        "next_step_prompt": "What would you try next, given that reminder?",
        "answer_revealed": False,
        "difficulty": 1,
    }


def _solution_json(payload: dict) -> dict:
    return {
        "steps": [
            {
                "step_number": 1,
                "explanation": f"Start from the question: {payload.get('question', '')}",
                "expression": payload.get("question", ""),
                "common_mistake": None,
            },
            {
                "step_number": 2,
                "explanation": "Apply the skill's standard method to isolate the answer.",
                "expression": "...",
                "common_mistake": "Forgetting to apply the operation to both sides.",
            },
        ],
        "final_answer": payload.get("selected_answer", ""),
    }


def _generated_template_json(payload: dict) -> dict:
    return {
        "shape_key": next(iter(payload.get("allowed_shape_keys", [])), "one_step_add"),
        "correct_option_generator": next(
            iter(payload.get("allowed_correct_option_generators", [])), "format_integer"
        ),
        "distractor_generator_keys": list(payload.get("allowed_distractor_generator_keys", []))[:3],
        "common_error_tags": ["mock_error_tag"],
        "estimated_time_seconds": 45,
        "reasoning": "mock generator",
    }


def _solver_json() -> dict:
    # Deterministic, doesn't attempt to actually solve the equation - tests that need to
    # exercise solver agreement/disagreement use a dedicated stub provider instead (see
    # test_bedrock_gateway.py's existing pattern for negative-path testing).
    return {"selected_option": "a", "reasoning": "mock solver"}


def _difficulty_review_json(payload: dict) -> dict:
    return {
        "difficulty_label": payload.get("proposed_difficulty", 1),
        "reasoning": "mock reviewer agrees with the proposed difficulty",
    }


def _ambiguity_review_json() -> dict:
    return {"is_ambiguous": False, "reasoning": "mock reviewer found no ambiguity"}


def _alignment_review_json() -> dict:
    return {"is_aligned": True, "reasoning": "mock reviewer confirms alignment"}


def _authored_generated_item_json(payload: dict) -> dict:
    """Deterministic S20 stand-in: a plausible, schema-valid authored item that always
    references the requested skill/difficulty in its stem, with a real 3-level hint
    ladder and a solution whose `final_answer` matches the declared `correct_option`
    (option "a") - tests that need to exercise disagreement/leakage/etc. inject a
    dedicated scripted gateway instead (same posture as `_solver_json`'s own docstring).

    D-238 added `proposed_difficulty`/`difficulty_rationale`, required since D-194 and
    missing here ever since, which had made this branch fail validation exactly like
    `_question_judge_json`'s. The generator proposes its own tier, so the mock echoes the
    requested one - the opposite of the judge, which must never see it.
    """
    skill_name = payload.get("skill_name", "this skill")
    difficulty = payload.get("difficulty_label", 1)
    return {
        "stem": f"Solve using {skill_name} (difficulty {difficulty}): what is 2 + 2?",
        "context_block": None,
        "option_a": "4",
        "option_b": "5",
        "option_c": "6",
        "option_d": "3",
        "correct_option": "a",
        "equation": "Eq(x, 2 + 2)",
        "hint_ladder": [
            "Think about combining two small groups of objects.",
            "Try counting up from 2 by 2 more.",
            "Add the two numbers together directly: 2 + 2.",
        ],
        "canonical_solution": {
            "steps": [
                {
                    "step_number": 1,
                    "explanation": "Add the two numbers.",
                    "expression": "2 + 2",
                    "common_mistake": None,
                }
            ],
            "final_answer": "4",
        },
        "misconception_tags": ["mock_misconception"],
        "estimated_time_seconds": 30,
        "proposed_difficulty": difficulty,
        "difficulty_rationale": (
            f"mock: written to the tier {difficulty} anchor for {skill_name}, one "
            f"operation, no rewriting before the arithmetic starts"
        ),
        "reasoning": "mock authored generator",
    }


def _question_judge_json(payload: dict) -> dict:
    """Deterministic §5.8.5 stand-in, rebuilt in D-238 after D-194's rename left it broken.

    It had emitted `difficulty_label` (the pre-D-194 name) and read `proposed_difficulty`
    from the payload - a field the *same* decision removed, precisely so the judge could
    not see the tier it was being asked to rate. So the branch both failed validation and
    encoded the blindness violation D-194 exists to prevent.

    `reviewed_difficulty` is a **stable hash of the question text, not a judgment.** Two
    properties are wanted and a constant has neither: the tiers must spread, so the
    audit's histogram, its `gap >= 2` arithmetic and `partition_findings`' new/known/
    lapsed/moot arms all actually execute under the mock; and they must not correlate with
    the declared tier, so no test can accidentally come to depend on the mock agreeing.
    Anything asserting on *which* tier comes back is asserting on a hash - use a scripted
    gateway for that, as `_solver_json` and `_authored_generated_item_json` both say.
    """
    question = str(payload.get("rendered_question", ""))
    reviewed = _stable_choice(question, (1, 2, 3, 4, 5))
    return {
        "reasoning": "mock judge: schema-valid stand-in, no model was consulted",
        "reviewed_difficulty": reviewed,
        "difficulty_reasoning": (
            f"mock: assigned tier {reviewed} from a hash of the stem, so the number is "
            f"stable across runs and independent of the declared tier"
        ),
        "is_ambiguous": False,
        "is_aligned": True,
        "is_age_appropriate": True,
        "is_internally_consistent": True,
        "hint_quality_score": 5,
        "hint_reveals_answer": False,
    }


def _learning_chat_intent_json(payload: dict) -> dict:
    """Deterministic S24 stand-in: picks a branch by keyword, same "good enough to be
    test-drivable" posture as `_scope_and_intent_json`. Checked in order of specificity
    (a message mentioning both "hint" and "video" resolves to "hint" first) so tests can
    rely on a stable precedence.
    """
    message = (payload.get("redacted_message") or "").lower()
    if any(k in message for k in ("hint", "clue", "stuck")):
        intent = "request_hint"
    elif any(k in message for k in ("solution", "steps", "show me how")):
        intent = "request_solution"
    elif "video" in message:
        intent = "request_video"
    elif any(k in message for k in ("wrong", "why is my answer", "why did i get")):
        intent = "why_wrong"
    elif any(k in message for k in ("help", "confused", "understand", "explain", "?")):
        intent = "question_help"
    else:
        intent = "off_topic"
    return {"intent": intent, "reasoning": "mock: matched a learning-chat keyword"}


def _tutor_chat_json(payload: dict) -> dict:
    skill = payload.get("skill", "this skill")
    reply: dict = {
        "reply_text": (
            f"Let's think through {skill} together - what part of this question feels "
            "trickiest right now?"
        ),
        "answer_revealed": False,
    }
    # D-217: emit a bounded `viz` when the student explicitly asks for a picture, so the
    # dev/test path exercises the whole viz round-trip deterministically (the real model
    # decides for itself whether a diagram helps).
    message = (payload.get("redacted_message") or "").lower()
    if any(k in message for k in ("picture", "diagram", "draw", "show me a")):
        reply["viz"] = {
            "kind": "bar_model",
            "caption": "The two sides of the equation, side by side.",
            "labels": ["Left side", "Right side"],
            "values": [12.0, 12.0],
        }
    return reply


_SUPPORTED_TOPIC_KEYWORDS = (
    "intellichoice",
    "branch",
    "volunteer",
    "student",
    "parent",
    "tutor",
    "calendar",
    "schedule",
    "attendance",
    "class",
    "program",
    "session",
    "learning",
    "handbook",
    "escalat",
    "admin",
    "location",
    "hour",
    "manager",
)


def _scope_and_intent_json(payload: dict) -> dict:
    """Deterministic §5.19.2 Scope Guard + Intent Router stand-in: a query is in-scope
    if it mentions any SPEC §5.19.4 supported-topic keyword; intent is picked by a
    second keyword pass over the same in-scope query. Real classification is a later
    real-model concern - this only needs to be deterministic and test-drivable.
    """
    query = (payload.get("standalone_query") or "").lower()
    if not any(keyword in query for keyword in _SUPPORTED_TOPIC_KEYWORDS):
        return {
            "in_scope": False,
            "intent": "clarification",
            "reasoning": "mock: no supported-topic keyword found",
        }
    if any(k in query for k in ("branch", "location", "near", "address")):
        intent = "branch_locator"
    elif any(k in query for k in ("calendar", "schedule", "holiday")):
        intent = "calendar"
    elif any(k in query for k in ("escalat", "speak to", "contact admin")):
        intent = "admin_contact"
    else:
        intent = "document_qa"
    return {
        "in_scope": True,
        "intent": intent,
        "reasoning": "mock: matched supported-topic keyword",
    }


def _rerank_json(payload: dict) -> dict:
    """Deterministic §5.21.7 reranker stand-in: scores each candidate by query-word
    overlap rather than any real cross-encoder - good enough to produce a stable,
    test-drivable order without a second model dependency.
    """
    query_words = {w for w in (payload.get("query") or "").lower().split() if len(w) > 2}
    scores = []
    for position, candidate in enumerate(payload.get("candidates", [])):
        text = (candidate.get("chunk_text") or "").lower()
        overlap = sum(1 for word in query_words if word in text)
        score = overlap / len(query_words) if query_words else 0.0
        scores.append(
            {
                "candidate_index": candidate.get("candidate_index", position),
                "relevance_score": round(score, 4),
            }
        )
    return {"scores": scores}


def _rag_answer_json(payload: dict) -> dict:
    """Deterministic §5.21.8 answer-synthesis stand-in. Always quotes a real, verifiable
    substring of the first context chunk (never invented text) so
    `chat_api.services.qa`'s grounding check passes for realistic mock-driven tests;
    with no context chunks it follows §5.29's "No RAG result -> do not guess, offer
    escalation" instead of fabricating an answer.
    """
    chunks = payload.get("context_chunks", [])
    if not chunks:
        return {
            "answer": "I don't have an approved source for that yet.",
            "citations": [],
            "confidence": 0.0,
            "missing_information": "No approved document covers this question.",
            "escalation_recommended": True,
        }
    top = chunks[0]
    text = top.get("chunk_text", "")
    quote = text[:80].strip() or text
    return {
        "answer": f"Based on the available documentation: {text[:200]}",
        "citations": [{"context_index": top.get("context_index", 0), "quote": quote}],
        "confidence": 0.8,
        "missing_information": None,
        "escalation_recommended": False,
    }


_MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}
_DATE_RE = re.compile(
    r"(?P<month>Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-zA-Z]*\.?\s+"
    r"(?P<day>\d{1,2})(?:-(?P<end_day>\d{1,2}))?,?\s+(?P<year>\d{4})"
)


def _calendar_extraction_json(payload: dict) -> dict:
    """Deterministic §5.23.2 extraction stand-in: finds the first "Month Day[-Day],
    Year" pattern in the top retrieved chunk's text (a real substring, never an
    invented date) and proposes it as the event. No match -> `found=False`, matching
    §5.29's "No RAG result -> do not guess".
    """
    chunks = payload.get("context_chunks", [])
    if not chunks:
        return {"found": False}
    top = chunks[0]
    text = top.get("chunk_text", "")
    match = _DATE_RE.search(text)
    if match is None:
        return {"found": False}
    month = _MONTHS[match.group("month").lower()]
    day = int(match.group("day"))
    end_day = int(match.group("end_day")) if match.group("end_day") else day
    year = int(match.group("year"))
    start = datetime(year, month, day, 9, 0)
    end = datetime(year, month, end_day, 17, 0)
    title_line = next((line.strip() for line in text.splitlines() if line.strip()), "Event")
    return {
        "found": True,
        "title": (title_line.lstrip("#").strip() or "Event")[:120],
        "start_datetime": start.isoformat(),
        "end_datetime": end.isoformat(),
        "timezone": "America/Los_Angeles",
        "location": None,
        "description": text[:200].strip(),
        "source_chunk_id": top.get("chunk_id"),
        "confidence": 0.85,
    }


def _video_classification_json(payload: dict) -> dict:
    """Deterministic §5.18 classification stand-in: proposes whichever known topic/
    skill names (the real allowlist the caller supplied) appear as a case-insensitive
    substring of the video's title+description - a stand-in for real judgment, but it
    never invents a name outside the menu it was given, matching this file's other
    "model picks from an explicit menu" mocks (e.g. `_generated_template_json`).
    """
    text = f"{payload.get('title', '')} {payload.get('description', '')}".lower()
    topic_names = [n for n in payload.get("known_topic_names", []) if n.lower() in text]
    skill_names = [n for n in payload.get("known_skill_names", []) if n.lower() in text]
    return {
        "topic_names": topic_names,
        "skill_names": skill_names,
        "grade_band": "3-5",
        "difficulty_min": 2,
        "difficulty_max": 4,
        "reasoning": "mock: keyword-matched known catalog names",
    }


def _memory_consolidation_json(payload: dict) -> dict:
    """Deterministic S25 consolidation stand-in: groups this window's events by skill
    and looks for a plain keyword signal in their code-rendered summaries -
    "unresolved" implies a `weak_skill` candidate, an all-`correct` `answer_submitted`
    group implies a `strength` candidate. Reuses a matching `existing_facts` entry (same
    `fact_type`+`skill_id`) as a `facts_to_update` reconfirmation instead of proposing a
    duplicate `facts_to_add` - good enough to exercise the add/update/provisional/
    contradiction-demotion paths deterministically without a real model. Never proposes
    `facts_to_expire` - the mock has no basis to judge staleness.
    """
    events = payload.get("events", [])
    existing_facts = payload.get("existing_facts", [])
    existing_by_key = {(f.get("fact_type"), f.get("skill_id")): f for f in existing_facts}

    by_skill: dict[str, list[dict]] = {}
    for event in events:
        skill_id = event.get("skill_id")
        if skill_id is None:
            continue
        by_skill.setdefault(skill_id, []).append(event)

    facts_to_add: list[dict] = []
    facts_to_update: list[dict] = []
    for skill_id, skill_events in by_skill.items():
        summaries = [(e.get("summary") or "").lower() for e in skill_events]
        event_ids = [e.get("event_id") for e in skill_events]

        if any("unresolved" in s for s in summaries):
            fact_type, polarity, text = (
                "weak_skill",
                "negative",
                "May need extra support with this skill - a recent attempt went unresolved.",
            )
            matches = lambda s: "unresolved" in s  # noqa: E731
        elif any("correct" in s and "incorrect" not in s for s in summaries):
            fact_type, polarity, text = (
                "strength",
                "positive",
                "Shows independent strength in this skill.",
            )
            matches = lambda s: "correct" in s and "incorrect" not in s  # noqa: E731
        else:
            continue

        cited_ids = [eid for eid, s in zip(event_ids, summaries, strict=True) if matches(s)]
        existing = existing_by_key.get((fact_type, skill_id))
        if existing is not None:
            facts_to_update.append(
                {
                    "semantic_memory_id": existing["semantic_memory_id"],
                    "fact_text": text,
                    "confidence": min(0.95, existing.get("confidence", 0.5) + 0.1),
                    "supporting_event_ids": cited_ids,
                }
            )
        else:
            facts_to_add.append(
                {
                    "fact_type": fact_type,
                    "skill_id": skill_id,
                    "topic_id": next(
                        (e.get("topic_id") for e in skill_events if e.get("topic_id")), None
                    ),
                    "fact_text": text,
                    "structured_value": {},
                    "polarity": polarity,
                    "confidence": 0.6,
                    "supporting_event_ids": cited_ids,
                }
            )

    return {
        "facts_to_add": facts_to_add,
        "facts_to_update": facts_to_update,
        "facts_to_expire": [],
    }


def _stage_narrative_json(payload: dict) -> dict:
    """Deterministic S26 narrative stand-in: builds one short sentence per stage from
    only the real fields already present in `payload` (never a fabricated number or
    name), so the output always round-trips `numeric_grounding.is_grounded` against the
    caller's own evidence dict without a real model.
    """
    stage = payload.get("stage")
    weak_skills = ", ".join(payload.get("weak_skill_names") or []) or None
    target_skill = payload.get("target_skill_name")
    completed_skill = payload.get("completed_skill_name")

    if stage == "pre_intro":
        text = "Welcome back! Let's see what you remember today."
    elif stage == "pre_outro":
        parts = []
        if payload.get("pre_raw_score") is not None:
            parts.append(f"You scored {payload['pre_raw_score']} on the pre-exam.")
        if weak_skills:
            parts.append(f"Let's strengthen {weak_skills}.")
        if target_skill:
            parts.append(f"Your study plan starts with {target_skill}.")
        text = " ".join(parts) or "Let's get started with your study plan."
    elif stage == "study_step":
        parts = []
        if completed_skill:
            parts.append(f"Nice work on {completed_skill}!")
        if target_skill:
            parts.append(f"Let's move on to {target_skill}.")
        text = " ".join(parts) or "Let's keep going."
    elif stage == "study_outro":
        parts = []
        if payload.get("hint_count") is not None:
            parts.append(f"You used {payload['hint_count']} hints")
        if payload.get("solution_count") is not None:
            parts.append(f"viewed {payload['solution_count']} solutions")
        summary = " and ".join(parts)
        text = (
            f"{summary} this session. Time for your post-exam!"
            if summary
            else "Great work studying today. Time for your post-exam!"
        )
    elif stage == "post_outro":
        parts = []
        if payload.get("pre_raw_score") is not None and payload.get("post_raw_score") is not None:
            parts.append(
                f"You went from {payload['pre_raw_score']} to {payload['post_raw_score']}."
            )
        if payload.get("raw_gain") is not None:
            parts.append(f"That's a gain of {payload['raw_gain']} points.")
        text = " ".join(parts) or "Great work completing your post-exam!"
    else:
        text = "Keep up the great work!"

    return {"narrative_text": text, "reasoning": ""}


def _report_interpretation_json(payload: dict) -> dict:
    """Deterministic S28 report stand-in: builds interpretation/recommendation
    sentences from only the real fields already present in `payload` (never a
    fabricated number or name), so the output always round-trips
    `numeric_grounding.is_grounded` against the caller's own evidence dict without a
    real model - same style as `_stage_narrative_json`.
    """
    weak_skills = ", ".join(payload.get("weak_skill_names") or []) or None

    interpretation_parts = []
    if payload.get("pre_raw_score") is not None and payload.get("post_raw_score") is not None:
        interpretation_parts.append(
            f"Score went from {payload['pre_raw_score']} to {payload['post_raw_score']}."
        )
    if payload.get("raw_gain") is not None:
        interpretation_parts.append(f"That's a gain of {payload['raw_gain']} points.")
    if weak_skills:
        interpretation_parts.append(f"Skills to strengthen: {weak_skills}.")
    interpretation_text = " ".join(interpretation_parts) or (
        "No verified activity in this date range yet."
    )

    recommendation_parts = []
    if weak_skills:
        recommendation_parts.append(f"Focus practice on {weak_skills}.")
    if payload.get("tutor_review_flagged"):
        recommendation_parts.append("A tutor review is recommended.")
    recommendations_text = " ".join(recommendation_parts) or "Keep up the regular practice."

    return {
        "interpretation_text": interpretation_text,
        "recommendations_text": recommendations_text,
        "reasoning": "",
    }


def _llm_judge_json(payload: dict) -> dict:
    """Deterministic S30 stand-in: scores every *requested* dimension (never invents
    ones the caller didn't ask for) at a fixed passing score, so a mock-driven judge
    run is test-drivable (scores line up 1:1 with `dimensions`) without a real model.
    A real judge's actual scores are unverified until real Bedrock creds exist - same
    "never exercised against real AWS" posture as D-025/D-035/D-046.
    """
    dimensions = payload.get("dimensions") or []
    scores = [
        {"dimension": dimension, "score": 4, "reasoning": f"mock: {dimension} looks adequate"}
        for dimension in dimensions
    ]
    return {"scores": scores, "overall_pass": True}


def _hint_solution_repair_json(payload: dict) -> dict:
    """Deterministic D-260 stand-in, and it must actually *repair* something.

    A mock that echoed the ladder back unchanged would make `review_loop`'s early stop fire on
    every item - the same defects would recur by construction - and every loop test would pass
    for the wrong reason. So it does the one repair the review mock's defect asks for: a rung
    that repeats its predecessor verbatim is rewritten. `_generic_json` cannot stand in here
    either, because `solution_steps` is a list of nested `SolutionStep` objects.
    """
    # `or [...]` rather than `or []`: `HintSolutionRepairResponse.hint_ladder` is
    # `min_length=1`, and the schema-conformance test calls every branch with an empty
    # payload. An empty list here was a real defect that test caught - the same fallback
    # already existed for `solution_steps` and was simply missed for the ladder.
    ladder = list(payload.get("hint_ladder") or ["mock repaired hint"])
    for index in range(1, len(ladder)):
        if ladder[index].strip() and ladder[index].strip() == ladder[index - 1].strip():
            ladder[index] = f"{ladder[index].rstrip('.')} - now think about what that gives you."
    steps = [
        {
            "step_number": position,
            "explanation": rendered.split("[")[0].strip().lstrip("0123456789. "),
            "expression": rendered.split("[")[-1].rstrip("]").strip(),
        }
        for position, rendered in enumerate(payload.get("solution_steps") or [], start=1)
    ]
    return {
        "reasoning": "mock repair: rewrote any rung that repeated its predecessor verbatim",
        "hint_ladder": ladder,
        "solution_steps": steps or [{"step_number": 1, "explanation": "mock", "expression": "x"}],
        "solution_final_answer": payload.get("solution_final_answer") or "unchanged",
    }


def _hint_solution_review_json(payload: dict) -> dict:
    """Deterministic D-251 stand-in. Passes by default so the mock does not silently gate
    every other test's fixtures, but stays *drivable*: an empty hint ladder or a rung that
    repeats its predecessor verbatim produces a located `repair`, so a test can exercise the
    defect path and the repair loop without a real model.

    `_generic_json` cannot stand in here - it would emit `verdict: "mock-verdict"`, which the
    `Literal` rejects, and the model validator would reject a defect-free `repair` besides.
    """
    ladder = payload.get("hint_ladder") or []
    defects = []
    if not ladder:
        defects.append(
            {
                "target": "hint_ladder",
                "index": None,
                "problem": "mock: the hint ladder is empty",
                "suggested_fix": "mock: add at least one rung",
            }
        )
    for n, (earlier, later) in enumerate(zip(ladder, ladder[1:], strict=False), start=2):
        if earlier.strip() and earlier.strip() == later.strip():
            defects.append(
                {
                    "target": "hint_ladder",
                    "index": n,
                    "problem": f"mock: rung {n} repeats rung {n - 1} verbatim",
                    "suggested_fix": "mock: make this rung add something new",
                }
            )
    return {
        "verdict": "repair" if defects else "pass",
        "defects": defects[:8],
        "uncertainty": "low",
        "reasoning": "mock: deterministic stand-in, not a judgement",
    }


def _generic_json(schema: dict) -> dict:
    result: dict = {}
    for name, prop in schema.get("properties", {}).items():
        prop_type = prop.get("type")
        if prop_type == "string":
            result[name] = f"mock-{name}"
        elif prop_type == "integer":
            result[name] = 1
        elif prop_type == "number":
            result[name] = 1.0
        elif prop_type == "boolean":
            result[name] = False
        elif prop_type == "array":
            result[name] = []
        else:
            result[name] = None
    return result


class MockBedrockProvider:
    """Deterministic - never raises, never times out - so it can be the default
    provider for both local dev and the test suite (SPEC §6.10's "safe fallbacks work"
    is exercised with a *different* test double that deliberately returns bad output;
    see `test_bedrock_gateway.py`).
    """

    async def raw_generate(
        self,
        *,
        model_id: str,
        system_prompt: str,
        user_message: str,
        json_schema: dict,
        max_output_tokens: int,
        tools: list[dict] | None = None,
        tool_executor: Callable[[str, dict], dict] | None = None,
        max_tool_rounds: int = 4,
    ) -> RawGeneration:
        # D-244. These three exist so the signature matches `AnthropicBedrockProvider`'s,
        # which D-202 widened when it gave the model a calculator during equation design.
        # The mock was never widened with it, so **every call that passes `tools` raised
        # `TypeError` at the provider boundary** - which the gateway catches as a provider
        # failure, meaning the design stage could not run under the mock at all and the only
        # way to exercise it was to pay. Same shape as D-238: a test double that cannot do
        # what production does turns a free path into a paid one, silently.
        #
        # Accepted and ignored rather than simulated. A mock tool loop would be a second
        # implementation of `execute_pipeline_tool`'s contract with nothing keeping the two
        # honest, and the value here is a deterministic response - not a rehearsal of the
        # round-trip, which `test_bedrock_gateway.py` already covers against a double built
        # for it.
        del model_id, system_prompt, max_output_tokens, tools, tool_executor, max_tool_rounds
        try:
            payload = json.loads(user_message)
        except ValueError:
            payload = {}

        title = json_schema.get("title")
        if title == "HintResponse":
            data = _hint_json(payload)
        elif title == "HintPersonalizationResponse":
            data = _hint_personalization_json(payload)
        elif title == "SolutionResponse":
            data = _solution_json(payload)
        elif title == "GeneratedTemplateResponse":
            data = _generated_template_json(payload)
        elif title == "SolverResponse":
            data = _solver_json()
        elif title == "DifficultyReviewResponse":
            data = _difficulty_review_json(payload)
        elif title == "AmbiguityReviewResponse":
            data = _ambiguity_review_json()
        elif title == "AlignmentReviewResponse":
            data = _alignment_review_json()
        elif title == "AuthoredGeneratedItemResponse":
            data = _authored_generated_item_json(payload)
        elif title == "QuestionJudgeResponse":
            data = _question_judge_json(payload)
        elif title == "ScopeAndIntentResponse":
            data = _scope_and_intent_json(payload)
        elif title == "RerankResponse":
            data = _rerank_json(payload)
        elif title == "RagAnswerResponse":
            data = _rag_answer_json(payload)
        elif title == "CalendarExtractionResponse":
            data = _calendar_extraction_json(payload)
        elif title == "VideoClassificationResponse":
            data = _video_classification_json(payload)
        elif title == "LearningChatIntentResponse":
            data = _learning_chat_intent_json(payload)
        elif title == "TutorChatResponse":
            data = _tutor_chat_json(payload)
        elif title == "MemoryUpdateResponse":
            data = _memory_consolidation_json(payload)
        elif title == "StageNarrativeResponse":
            data = _stage_narrative_json(payload)
        elif title == "ReportInterpretationResponse":
            data = _report_interpretation_json(payload)
        elif title == "LlmJudgeResponse":
            data = _llm_judge_json(payload)
        elif title == "HintSolutionReviewResponse":
            data = _hint_solution_review_json(payload)
        elif title == "HintSolutionRepairResponse":
            data = _hint_solution_repair_json(payload)
        else:
            data = _generic_json(json_schema)

        text = json.dumps(data)
        return RawGeneration(
            text=text, input_tokens=len(user_message) // 4, output_tokens=len(text) // 4
        )

    async def raw_embed(self, *, model_id: str, texts: list[str]) -> RawEmbedding:
        del model_id
        vectors = [_deterministic_vector(text) for text in texts]
        return RawEmbedding(vectors=vectors, input_tokens=sum(len(text) // 4 for text in texts))


def _deterministic_vector(text: str) -> list[float]:
    """Same text always produces the same vector (no real semantic content, but
    reproducible - matches D-016's seed-reproducibility convention for the curriculum
    generator). Hash-seeded rather than `hash(text)` since Python's string hashing is
    randomized per-process by default.
    """
    seed = int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")
    rng = random.Random(seed)
    raw = [rng.uniform(-1.0, 1.0) for _ in range(_MOCK_EMBEDDING_DIM)]
    norm = sum(v * v for v in raw) ** 0.5
    return [v / norm for v in raw]
