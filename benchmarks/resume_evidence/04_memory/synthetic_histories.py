"""E4.1 - the synthetic student-history generator with planted ground truth.

Measurement code, not shipped code: `benchmarks/` is outside the uv workspace on purpose,
so nothing here can be imported by product code even by accident. Loaded by path
(`importlib.util.spec_from_file_location`) by `memory_benchmark.py` and by the tests in
`packages/memory/tests/test_synthetic_histories.py`, the same way E5.1's and E6.1's
harnesses are.

## What this generates

A corpus of synthetic students, each with a multi-week `learning_events` history that the
S25 consolidation worker (`intellichoice_memory.consolidation`) can be run over window by
window, plus a **manifest of what each student's memory should end up containing**. The
manifest is the ground truth every quality number in E4 is scored against; without it
there is nothing to score, which is exactly the state Theme 4 was in before this file.

## Two layers, deliberately split

- **Planning is pure** (`plan_corpus`): no database, no I/O, no clock. A `StudentPlan` is
  a value, so determinism is testable in-process at ~0 cost and a re-run with the same
  seed reproduces the corpus bit for bit. Every random draw comes from a per-student
  `random.Random(f"{seed}:{index}")`, so a student's history does not depend on how many
  students were asked for - `plan_corpus(n=25)` is a strict prefix of `plan_corpus(n=1000)`.
  That is what lets the real-model arm (E4.2, N=25) run against the *same* students the
  mock arm (E4.1, N=1000) ran, rather than a differently-shaped corpus.
- **Writing is I/O** (`write_corpus`): resolves skill slots to real `skills.skill_id`
  values, window/offset to real `occurred_at` timestamps, and inserts through
  `MemoryRepository.record_event` - the same call `learning_api.services.memory_events`
  uses, so the rows are the rows the product writes and not a bench-only shape.

## Distributions, and where each number comes from

Nothing here is a round number somebody liked. The two sources are the only real-data
shape anchors this project has:

- **events per session: 30-68, uniform** - `U7_CHECKPOINT_CONSOLIDATION.md` §2.2, the
  9 completed staging threads, which is the only real per-session count this project has.
- **sessions per window: 1-2** - U7's own growth model assumes 4 sessions per student per
  month; over a 7-day window that is one to two.
- **windows: 3** - the minimum that can express the two-stage contradiction protocol
  (`consolidation.py:633-670`): create, contradict, contradict again.
- **heavy-tail events/window: 1,500** - above the ~857-event point where
  `_MAX_CALLS_PER_STUDENT=4` starts dropping (60,000 chars per call, ~280 chars per
  serialised event, four calls).
- **extreme-tail events/window: 4,600** - ~13,800 over three windows, against AUD-F-34's
  real **13,865** events for one student-week (D-141 §5).
- **chat-turn share: 20%** - D-141 §5 records ~12,000 of those 13,865 events as
  `chat_turn`. 20% is deliberately conservative for a standard student; the extreme-tail
  class carries the chat-dominated shape.

## The planted scenarios

Each standard student gets one instance of each scenario below, on its **own** skill -
because a fact's natural key is `(student, fact_type, skill_id)` (`find_live_fact`), two
scenarios sharing a skill would interfere and neither would be scoreable.

- **`repeated_weak`** - 2 `unresolved` in w0, 2 in w1 (different sessions). Provisional
  after w0, promoted to **active** at w1 (>=3 events across >=2 sessions).
- **`under_evidenced`** - 2 `unresolved`, one session, w0 only. Stays **provisional**
  forever, and `top_fact_for_skill` must return None for it.
- **`repeated_strength`** - 2 correct answers in w0, 2 in w1. **Active** `strength`.
- **`mastery_conflict_weak`** - 3 `unresolved` across w0/w1 plus a **0.92** mastery row.
  The candidate is refused by `_contradicts_measured_mastery`; **no live fact**.
- **`mastery_conflict_strength`** - 3 correct across w0/w1 plus a **0.25** mastery row.
  Same screen, the other direction; **no live fact**.
- **`polarity_flip`** - correct in w0 and w1, then `unresolved` in w2. The *later*
  negative signal should be what the tutor is served.
- **`irrelevant`** - chat / exam-finalized / gain events with no skill. No fact should be
  keyed to any of them.

`polarity_flip` is the one whose expectation is **not** a prediction of the current code -
see `memory_benchmark.py`'s report for what it actually measures. It is planted as a
question, not as an assertion.

## Safety

Student ids are `bench-student-<n>` strings. Chat text is drawn from a fixed pool of
seven generic math-help sentences with no name, no contact detail and no free text of any
kind - see `_CHAT_MESSAGES`. Nothing in this file reads a fixture, a database, or any
existing row, so no real or fixture-derived PII can reach the corpus.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import pathlib
import random
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

# --- the closed event vocabulary, restated as literals ---------------------------------
#
# Deliberately NOT imported from `intellichoice_memory.events`. This generator's job is to
# emit the payload shapes the *emitter* writes, and importing the renderer's constants
# would make a generator that agrees with the renderer by construction - which is the same
# "correct because it shares the fixture's own keywords" trap the mock provider falls into
# and that E4.1 exists to stay out of. `test_synthetic_histories.py` asserts these strings
# still equal the product constants, so a drift fails a test instead of passing silently.
ANSWER_SUBMITTED = "answer_submitted"
INTERVENTION_CHOSEN = "intervention_chosen"
STUDY_OUTCOME = "study_outcome"
CHAT_TURN = "chat_turn"
EXAM_FINALIZED = "exam_finalized"
LEARNING_GAIN_COMPUTED = "learning_gain_computed"

# `study_outcomes.py`'s labels. `unresolved` is the one the retry ladder ends on when a
# skill line never resolved, and it is the negative signal every `weak_skill` scenario
# below is built from.
OUTCOME_UNRESOLVED = "unresolved"
OUTCOME_INDEPENDENT_CORRECT = "independent_correct"
OUTCOME_CORRECT_AFTER_HINT = "correct_after_hint"

# `LearningChatIntentResponse`'s enum.
CHAT_INTENTS = ("question_help", "request_hint", "why_wrong", "request_video", "off_topic")

# Seven fixed sentences, no names, no contact details, no numbers that could identify
# anyone. Realistic *length* matters (chat text is the token-dominant event type in the
# AUD-F-34 shape), realistic content does not.
_CHAT_MESSAGES = (
    "How do I solve step 2 of this problem?",
    "I do not understand why the sign changes when both sides are divided.",
    "Can you show me a worked example that looks like this one?",
    "Why was my answer marked wrong when I got the same number?",
    "What is the difference between this and the previous question?",
    "I keep getting stuck at the part where the fractions are combined.",
    "Is there a shorter way to check the answer once I have it?",
)

SCENARIO_REPEATED_WEAK = "repeated_weak"
SCENARIO_UNDER_EVIDENCED = "under_evidenced"
SCENARIO_REPEATED_STRENGTH = "repeated_strength"
SCENARIO_MASTERY_CONFLICT_WEAK = "mastery_conflict_weak"
SCENARIO_MASTERY_CONFLICT_STRENGTH = "mastery_conflict_strength"
SCENARIO_POLARITY_FLIP = "polarity_flip"
SCENARIO_IRRELEVANT = "irrelevant"

SCENARIOS = (
    SCENARIO_REPEATED_WEAK,
    SCENARIO_UNDER_EVIDENCED,
    SCENARIO_REPEATED_STRENGTH,
    SCENARIO_MASTERY_CONFLICT_WEAK,
    SCENARIO_MASTERY_CONFLICT_STRENGTH,
    SCENARIO_POLARITY_FLIP,
    SCENARIO_IRRELEVANT,
)

CLASS_STANDARD = "standard"
CLASS_HEAVY_TAIL = "heavy_tail"
CLASS_EXTREME_TAIL = "extreme_tail"


@dataclass(frozen=True)
class CorpusConfig:
    """Every knob, in one recorded value - written verbatim into the manifest header so a
    result can never be read without the configuration that produced it.
    """

    students: int = 1000
    seed: int = 20260828
    windows: int = 3
    window_days: int = 7
    sessions_per_window: tuple[int, int] = (1, 2)
    events_per_session: tuple[int, int] = (30, 68)
    # Fraction of filler `answer_submitted` events that are correct. 0.62 is the recorded
    # large-run acceptance shape from a different pipeline, used here only as a plausible
    # mid-range value; nothing in E4 is sensitive to it beyond how many unplanted extras
    # the filler skills generate.
    correct_rate: float = 0.62
    chat_turn_share: float = 0.20
    catalog_skills: int = 30
    # 30 skills, at most one live fact per (fact_type, skill) - so a student with facts on
    # many skills can cross `MemoryUpdateResponse.MAX_SAFE_EXISTING_FACTS` (21), which is
    # the `memory_consolidation_payload_oversized` condition. Measured rather than assumed.
    planted_skills_per_student: int = 6
    filler_skills_per_student: int = 8
    heavy_tail_students: int = 10
    heavy_tail_events_per_window: int = 1500
    extreme_tail_students: int = 5
    extreme_tail_events_per_window: int = 4600

    def as_dict(self) -> dict:
        return dataclasses.asdict(self)


@dataclass(frozen=True)
class EventPlan:
    window: int
    session_index: int
    event_type: str
    skill_slot: int | None
    payload: dict
    offset_minutes: int
    # True for the events a planted scenario depends on. Filler is never scored; a scorer
    # that could not tell the two apart would be scoring its own noise.
    planted_for: str | None = None


@dataclass(frozen=True)
class PlantedFact:
    """One scoreable expectation.

    `expected_status is None` means "no live fact for this (student, skill) at all" - the
    correct outcome for both mastery-conflict scenarios, where the whole point is that
    nothing is written.
    """

    scenario: str
    skill_slot: int
    expected_fact_type: str | None
    expected_polarity: str | None
    expected_status: str | None
    expected_served: bool
    rationale: str


@dataclass(frozen=True)
class StudentPlan:
    external_id: str
    student_class: str
    planted_slots: tuple[int, ...]
    filler_slots: tuple[int, ...]
    mastery: tuple[tuple[int, float], ...]
    events: tuple[EventPlan, ...]
    planted: tuple[PlantedFact, ...]

    def events_for_window(self, window: int) -> list[EventPlan]:
        return [e for e in self.events if e.window == window]


def _chat_payload(rng: random.Random, message_slot: int) -> dict:
    return {
        "intent": rng.choice(CHAT_INTENTS),
        "resolved": rng.random() < 0.7,
        # Resolved to a real `tutor_chat_messages.message_id` by `write_corpus`; the
        # plan carries only the pool index, so planning stays pure.
        "chat_message_slot": message_slot,
    }


def _plan_student(index: int, config: CorpusConfig, student_class: str) -> StudentPlan:
    """One student's whole history, from one seed. Pure."""
    rng = random.Random(f"{config.seed}:{index}")
    external_id = f"bench-student-{index:05d}"

    slots = list(range(config.catalog_skills))
    rng.shuffle(slots)
    planted_slots = tuple(slots[: config.planted_skills_per_student])
    filler_slots = tuple(
        slots[
            config.planted_skills_per_student : config.planted_skills_per_student
            + config.filler_skills_per_student
        ]
    )

    events: list[EventPlan] = []
    planted: list[PlantedFact] = []
    mastery: list[tuple[int, float]] = []
    # A per-student monotonic minute cursor inside each window, so `occurred_at` ordering
    # is well defined - `_batch_summaries` relies on chronological order being real
    # (D-141 §1: "chronological order is load-bearing").
    clock = {w: 0 for w in range(config.windows)}

    def _next_offset(window: int) -> int:
        clock[window] += rng.randint(1, 9)
        return clock[window]

    def _add(
        window: int,
        session_index: int,
        event_type: str,
        skill_slot: int | None,
        payload: dict,
        planted_for: str | None = None,
    ) -> None:
        events.append(
            EventPlan(
                window=window,
                session_index=session_index,
                event_type=event_type,
                skill_slot=skill_slot,
                payload=payload,
                offset_minutes=_next_offset(window),
                planted_for=planted_for,
            )
        )

    sessions_per_window = {
        w: rng.randint(*config.sessions_per_window) for w in range(config.windows)
    }

    # --- filler first, so planted events interleave into a realistic stream -------------
    if student_class == CLASS_STANDARD:
        for window in range(config.windows):
            for session_index in range(sessions_per_window[window]):
                for _ in range(rng.randint(*config.events_per_session)):
                    _add(window, session_index, *_filler_event(rng, filler_slots, config))
            # One exam-finalize and one gain per window: the two session-level events the
            # product emits once per cycle, and the `irrelevant` scenario's own material.
            _add(
                window,
                0,
                EXAM_FINALIZED,
                None,
                {"session_type": "post_exam", "raw_score": round(rng.uniform(0.35, 0.95), 2)},
                planted_for=SCENARIO_IRRELEVANT,
            )
            _add(
                window,
                0,
                LEARNING_GAIN_COMPUTED,
                None,
                {
                    "weighted_gain": round(rng.uniform(-0.1, 0.4), 3),
                    "unresolved_skills": [],
                },
                planted_for=SCENARIO_IRRELEVANT,
            )
    else:
        per_window = (
            config.heavy_tail_events_per_window
            if student_class == CLASS_HEAVY_TAIL
            else config.extreme_tail_events_per_window
        )
        # The tail classes are chat-dominated, which is the AUD-F-34 shape: ~12,000 of
        # 13,865 events were `chat_turn` (D-141 §5). They carry no planted scenarios -
        # what they measure (the call cap, `events_dropped`, the input ceiling) is
        # provider-independent and needs no ground truth.
        for window in range(config.windows):
            for i in range(per_window):
                if i % 10 < 8:
                    _add(
                        window,
                        i % max(sessions_per_window[window], 1),
                        CHAT_TURN,
                        None,
                        _chat_payload(rng, rng.randrange(len(_CHAT_MESSAGES))),
                    )
                else:
                    _add(
                        window,
                        i % max(sessions_per_window[window], 1),
                        *_filler_event(rng, filler_slots, config),
                    )

    if student_class != CLASS_STANDARD:
        return StudentPlan(
            external_id=external_id,
            student_class=student_class,
            planted_slots=(),
            filler_slots=filler_slots,
            mastery=(),
            events=tuple(sorted(events, key=lambda e: (e.window, e.offset_minutes))),
            planted=(),
        )

    # --- the planted scenarios ----------------------------------------------------------
    (
        slot_repeated_weak,
        slot_under_evidenced,
        slot_repeated_strength,
        slot_conflict_weak,
        slot_conflict_strength,
        slot_flip,
    ) = planted_slots

    def _unresolved(window: int, session_index: int, slot: int, scenario: str) -> None:
        _add(
            window,
            session_index,
            STUDY_OUTCOME,
            slot,
            {"outcome_label": OUTCOME_UNRESOLVED, "target_skill_slot": slot},
            planted_for=scenario,
        )

    def _correct_answer(window: int, session_index: int, slot: int, scenario: str) -> None:
        _add(
            window,
            session_index,
            ANSWER_SUBMITTED,
            slot,
            {
                "is_correct": True,
                "response_time_ms": rng.randint(3_000, 30_000),
                "phase": "study",
            },
            planted_for=scenario,
        )

    # repeated_weak: 2 events in w0, 2 in w1 -> 4 events over 2 sessions -> active at w1.
    for _ in range(2):
        _unresolved(0, 0, slot_repeated_weak, SCENARIO_REPEATED_WEAK)
    for _ in range(2):
        _unresolved(1, 0, slot_repeated_weak, SCENARIO_REPEATED_WEAK)
    planted.append(
        PlantedFact(
            scenario=SCENARIO_REPEATED_WEAK,
            skill_slot=slot_repeated_weak,
            expected_fact_type="weak_skill",
            expected_polarity="negative",
            expected_status="active",
            expected_served=True,
            rationale="4 supporting events across 2 sessions clears MIN_EVIDENCE_EVENTS=3 / "
            "MIN_EVIDENCE_SESSIONS=2, so promote_if_eligible must lift it out of provisional",
        )
    )

    # under_evidenced: 2 events, ONE session, w0 only -> never clears the bar.
    for _ in range(2):
        _unresolved(0, 0, slot_under_evidenced, SCENARIO_UNDER_EVIDENCED)
    planted.append(
        PlantedFact(
            scenario=SCENARIO_UNDER_EVIDENCED,
            skill_slot=slot_under_evidenced,
            expected_fact_type="weak_skill",
            expected_polarity="negative",
            expected_status="provisional",
            expected_served=False,
            rationale="2 events in 1 session is below both thresholds; a provisional fact must "
            "never be returned by top_fact_for_skill (it is not served to any payload)",
        )
    )

    # repeated_strength: the positive mirror of repeated_weak.
    for _ in range(2):
        _correct_answer(0, 0, slot_repeated_strength, SCENARIO_REPEATED_STRENGTH)
    for _ in range(2):
        _correct_answer(1, 0, slot_repeated_strength, SCENARIO_REPEATED_STRENGTH)
    planted.append(
        PlantedFact(
            scenario=SCENARIO_REPEATED_STRENGTH,
            skill_slot=slot_repeated_strength,
            expected_fact_type="strength",
            expected_polarity="positive",
            expected_status="active",
            expected_served=True,
            rationale="same evidence bar as repeated_weak, opposite polarity",
        )
    )

    # mastery_conflict_weak: a measured-strong skill with a weak-looking history.
    for _ in range(2):
        _unresolved(0, 0, slot_conflict_weak, SCENARIO_MASTERY_CONFLICT_WEAK)
    _unresolved(1, 0, slot_conflict_weak, SCENARIO_MASTERY_CONFLICT_WEAK)
    mastery.append((slot_conflict_weak, 0.92))
    planted.append(
        PlantedFact(
            scenario=SCENARIO_MASTERY_CONFLICT_WEAK,
            skill_slot=slot_conflict_weak,
            expected_fact_type=None,
            expected_polarity=None,
            expected_status=None,
            expected_served=False,
            rationale="AUD-L-13: a weak_skill claim about a skill measured at 0.92 (>= "
            "WEAK_SKILL_THRESHOLD 0.7) contradicts the measurement and must be refused, "
            "however many events support it",
        )
    )

    # mastery_conflict_strength: the mirror - a measured-weak skill with a strong history.
    for _ in range(2):
        _correct_answer(0, 0, slot_conflict_strength, SCENARIO_MASTERY_CONFLICT_STRENGTH)
    _correct_answer(1, 0, slot_conflict_strength, SCENARIO_MASTERY_CONFLICT_STRENGTH)
    mastery.append((slot_conflict_strength, 0.25))
    planted.append(
        PlantedFact(
            scenario=SCENARIO_MASTERY_CONFLICT_STRENGTH,
            skill_slot=slot_conflict_strength,
            expected_fact_type=None,
            expected_polarity=None,
            expected_status=None,
            expected_served=False,
            rationale="the direction AUD-L-13 was actually filed for: a strength fact for a "
            "skill measured at 0.25 is the `aud-student-regressing` reproduction",
        )
    )

    # polarity_flip: consistent success, then consistent failure. The expectation recorded
    # here is the PRODUCT one ("the tutor should be told about the regression"), not a
    # prediction about the current implementation - see the module docstring.
    for _ in range(2):
        _correct_answer(0, 0, slot_flip, SCENARIO_POLARITY_FLIP)
    for _ in range(2):
        _correct_answer(1, 0, slot_flip, SCENARIO_POLARITY_FLIP)
    # Four regression events across TWO sessions, so the negative claim clears the same
    # evidence bar the positive one did. Without that the scenario would confound two
    # different mechanisms - "the contradiction did not demote" and "the new fact was
    # under-evidenced" - and a measurement that cannot tell those apart is not worth
    # taking. Session indices are forced rather than drawn: a window whose filler happens
    # to occupy one session would otherwise silently make the bar unreachable.
    for i in range(4):
        _unresolved(2, i % 2, slot_flip, SCENARIO_POLARITY_FLIP)
    planted.append(
        PlantedFact(
            scenario=SCENARIO_POLARITY_FLIP,
            skill_slot=slot_flip,
            expected_fact_type="weak_skill",
            expected_polarity="negative",
            expected_status="active",
            expected_served=True,
            rationale="after a sustained regression in the final window, what the tutor is "
            "served for this skill should reflect the regression, not the earlier strength",
        )
    )

    return StudentPlan(
        external_id=external_id,
        student_class=student_class,
        planted_slots=planted_slots,
        filler_slots=filler_slots,
        mastery=tuple(mastery),
        events=tuple(sorted(events, key=lambda e: (e.window, e.offset_minutes))),
        planted=tuple(planted),
    )


def _filler_event(
    rng: random.Random, filler_slots: tuple[int, ...], config: CorpusConfig
) -> tuple[str, int | None, dict]:
    """One realistic non-scored event. Returns `(event_type, skill_slot, payload)`.

    Filler is not neutral and is not meant to be: it lands on `filler_slots`, which are
    disjoint from every planted slot, and it will legitimately cause a consolidator to
    propose facts about those skills. Those are counted as **unplanted extras**, which is
    the honest category for them - a fact supported by real events about a real skill is
    not an error just because this generator did not ask for it.
    """
    roll = rng.random()
    if roll < config.chat_turn_share:
        return CHAT_TURN, None, _chat_payload(rng, rng.randrange(len(_CHAT_MESSAGES)))
    if roll < config.chat_turn_share + 0.45:
        slot = rng.choice(filler_slots)
        return (
            ANSWER_SUBMITTED,
            slot,
            {
                "is_correct": rng.random() < config.correct_rate,
                "response_time_ms": rng.randint(2_000, 90_000),
                "phase": rng.choice(("pre_exam", "study", "post_exam")),
            },
        )
    if roll < config.chat_turn_share + 0.70:
        slot = rng.choice(filler_slots)
        return (
            INTERVENTION_CHOSEN,
            slot,
            {
                "choice": rng.choice(("hint", "video", "solution", "no")),
                "hint_level": rng.choice((None, 1, 2, 3)),
            },
        )
    slot = rng.choice(filler_slots)
    return (
        STUDY_OUTCOME,
        slot,
        {
            "outcome_label": rng.choice(
                (
                    OUTCOME_INDEPENDENT_CORRECT,
                    OUTCOME_CORRECT_AFTER_HINT,
                    OUTCOME_UNRESOLVED,
                )
            ),
            "target_skill_slot": slot,
        },
    )


def plan_corpus(config: CorpusConfig) -> list[StudentPlan]:
    """The whole corpus as values. Pure, deterministic, and prefix-stable in `students`.

    Class assignment is by **index**, not by draw, which is what makes the prefix property
    hold: student 3 is the same student whether 25 or 1,000 were asked for. The tail
    classes are therefore placed at fixed low indices so a small N still contains them if
    it wants them - and `stratified_subset` below is what the real arm actually uses.
    """
    tail_indices: dict[int, str] = {}
    for i in range(config.heavy_tail_students):
        tail_indices[i * 97 + 3] = CLASS_HEAVY_TAIL
    for i in range(config.extreme_tail_students):
        tail_indices[i * 193 + 11] = CLASS_EXTREME_TAIL
    return [
        _plan_student(i, config, tail_indices.get(i, CLASS_STANDARD))
        for i in range(config.students)
    ]


def stratified_subset(plans: list[StudentPlan], size: int) -> list[StudentPlan]:
    """The first `size` **standard** students, in index order.

    Deliberately excludes the two tail classes. What a tail student measures - the
    `_MAX_CALLS_PER_STUDENT` cap, `events_dropped`, and whether the raw history clears the
    gateway's 32,000-token input ceiling - is entirely provider-independent and is fully
    measured by the mock arm at N=1,000. Paying a real model four calls per window per tail
    student to re-measure a deterministic bound would spend a third of E4.2's budget on a
    number E4.1 already has exactly. Recorded here rather than in the report alone, because
    the composition of a 25-student sample is the sort of thing that gets read as an
    oversight when it is a decision.
    """
    return [p for p in plans if p.student_class == CLASS_STANDARD][:size]


# --- database side ---------------------------------------------------------------------

CATALOG_TOPIC_NAME = "E4 Benchmark Topic"
CATALOG_SKILL_PREFIX = "e4-bench-skill"


@dataclass
class WrittenCorpus:
    """What `write_corpus` resolved, so the scorer can map slots back to real ids."""

    topic_id: str
    skill_ids: list[str]
    window_bounds: list[tuple[datetime, datetime]]
    events_written: int = 0
    chat_messages_written: int = 0
    mastery_rows_written: int = 0
    # student_external_id -> {skill_slot -> [event_id, ...]} for planted events only.
    planted_event_ids: dict[str, dict[int, list[str]]] = field(default_factory=dict)


async def seed_catalog(session, config: CorpusConfig) -> tuple[str, list[str]]:
    """One topic and `catalog_skills` skills, shared by every student.

    Skills are curriculum-level rows, not student-level ones, so sharing them across the
    corpus is what the product does too; facts are keyed by `(student, fact_type, skill)`,
    so two students on the same skill cannot interfere.
    """
    from intellichoice_db.models.curriculum import Skill, Topic
    from intellichoice_db.repositories.curriculum import CurriculumRepository

    curriculum = CurriculumRepository(session)
    topic = await curriculum.create_topic(
        Topic(curriculum_version="e4-bench", name=CATALOG_TOPIC_NAME, grade_band="6-8")
    )
    skill_ids = []
    for i in range(config.catalog_skills):
        skill = await curriculum.create_skill(
            Skill(topic_id=topic.topic_id, name=f"{CATALOG_SKILL_PREFIX}-{i:02d}")
        )
        skill_ids.append(skill.skill_id)
    return topic.topic_id, skill_ids


def window_bounds(config: CorpusConfig, corpus_start: datetime) -> list[tuple[datetime, datetime]]:
    """`[start, end)` per window, matching `consolidate_cli`'s rolling-window semantics.

    Windows are contiguous and non-overlapping, so `list_events_in_window` partitions the
    student's history exactly - a benchmark whose windows overlapped would consolidate the
    same event twice and report a compression ratio for a history that was never sent.
    """
    return [
        (
            corpus_start + timedelta(days=config.window_days * w),
            corpus_start + timedelta(days=config.window_days * (w + 1)),
        )
        for w in range(config.windows)
    ]


async def write_corpus(
    session,
    plans: list[StudentPlan],
    config: CorpusConfig,
    *,
    corpus_start: datetime,
    topic_id: str,
    skill_ids: list[str],
    progress_every: int = 100,
    log=print,
) -> WrittenCorpus:
    """Insert one planned corpus. Every event goes through `MemoryRepository.record_event`.

    Using the product's own writer rather than a bulk `INSERT` is the point: the rows this
    benchmark consolidates are then indistinguishable from the rows
    `learning_api.services.memory_events` writes, so nothing measured downstream can be an
    artefact of a bench-only row shape. It costs one round trip per event (`record_event`
    flushes), which is the price of that property.
    """
    from intellichoice_db.models.mastery import Mastery
    from intellichoice_db.models.memory import LearningEvent
    from intellichoice_db.models.tutor_chat import TutorChatMessage
    from intellichoice_db.repositories.memory import MemoryRepository

    memory_repo = MemoryRepository(session)
    bounds = window_bounds(config, corpus_start)
    written = WrittenCorpus(topic_id=topic_id, skill_ids=skill_ids, window_bounds=bounds)

    for n, plan in enumerate(plans, start=1):
        planted_ids: dict[int, list[str]] = {}
        for slot, score in plan.mastery:
            session.add(
                Mastery(
                    student_external_id=plan.external_id,
                    skill_id=skill_ids[slot],
                    raw_accuracy=score,
                    weighted_score=score,
                    accuracy_by_difficulty={},
                )
            )
            written.mastery_rows_written += 1
        await session.flush()

        for event in plan.events:
            window_start = bounds[event.window][0]
            occurred_at = window_start + timedelta(minutes=event.offset_minutes)
            payload = dict(event.payload)
            skill_id = skill_ids[event.skill_slot] if event.skill_slot is not None else None
            if "target_skill_slot" in payload:
                payload["target_skill_id"] = skill_ids[payload.pop("target_skill_slot")]
            if event.event_type == CHAT_TURN:
                message = TutorChatMessage(
                    student_external_id=plan.external_id,
                    learning_session_id=_session_id(plan, event),
                    intent=payload["intent"],
                    redacted_student_message=_CHAT_MESSAGES[payload.pop("chat_message_slot")],
                    reply_text="Let us work through that one step at a time.",
                    created_at=occurred_at,
                )
                session.add(message)
                await session.flush()
                payload["tutor_chat_message_id"] = message.message_id
                written.chat_messages_written += 1
            row = await memory_repo.record_event(
                LearningEvent(
                    student_external_id=plan.external_id,
                    session_id=_session_id(plan, event),
                    event_type=event.event_type,
                    topic_id=topic_id if event.skill_slot is not None else None,
                    skill_id=skill_id,
                    structured_payload=payload,
                    occurred_at=occurred_at,
                )
            )
            written.events_written += 1
            if event.planted_for is not None and event.skill_slot is not None:
                planted_ids.setdefault(event.skill_slot, []).append(row.event_id)
        written.planted_event_ids[plan.external_id] = planted_ids
        if progress_every and n % progress_every == 0:
            # Commit and forget, every `progress_every` students. Not cosmetic: without it
            # the whole corpus (400,000+ ORM objects at N=1,000) lives in one session's
            # identity map inside one transaction, which costs hundreds of MB of Python
            # heap and holds a write transaction open for the length of the seed. Neither
            # is a property of the thing being measured, and both are avoidable by
            # committing work that is already final - a seeded row is never revised.
            await session.commit()
            session.expunge_all()
            log(f"  wrote {n}/{len(plans)} students, {written.events_written} events")
    await session.commit()
    session.expunge_all()
    return written


def _session_id(plan: StudentPlan, event: EventPlan) -> str:
    return f"{plan.external_id}-w{event.window}-s{event.session_index}"


def _scenario_rationales() -> dict[str, str]:
    """One representative student's rationales, keyed by scenario.

    Built from a fixed tiny corpus rather than from the caller's, because the rationale
    text is identical for every student by construction and this keeps the header
    independent of which corpus is being written.
    """
    sample = _plan_student(0, CorpusConfig(students=1), CLASS_STANDARD)
    return {fact.scenario: fact.rationale for fact in sample.planted}


def write_manifest(path: pathlib.Path, config: CorpusConfig, plans: list[StudentPlan]) -> None:
    """One JSONL line per student, preceded by a header line carrying the configuration.

    The header is a line rather than a sidecar file because a manifest that can be read
    without its configuration is a manifest whose numbers can be quoted without their
    denominators - the failure the measurement plan's evidence rules exist to prevent.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "record": "corpus_header",
                    "config": config.as_dict(),
                    "students": len(plans),
                    "scenarios": list(SCENARIOS),
                    # Each scenario's rationale is a property of the SCENARIO, not of the
                    # student, so it belongs here once rather than repeated on every
                    # student row - where at N=1,000 it was a megabyte of identical prose.
                    "scenario_rationales": _scenario_rationales(),
                }
            )
            + "\n"
        )
        for plan in plans:
            fh.write(
                json.dumps(
                    {
                        "record": "student",
                        "student_external_id": plan.external_id,
                        "student_class": plan.student_class,
                        "event_count": len(plan.events),
                        "windows": {
                            str(w): sum(1 for e in plan.events if e.window == w)
                            for w in range(config.windows)
                        },
                        "mastery": [
                            {"skill_slot": slot, "weighted_score": score}
                            for slot, score in plan.mastery
                        ],
                        "planted": [
                            {k: v for k, v in dataclasses.asdict(p).items() if k != "rationale"}
                            for p in plan.planted
                        ],
                    }
                )
                + "\n"
            )


def corpus_fingerprint(plans: list[StudentPlan]) -> str:
    """A cheap, order-sensitive digest of a planned corpus - what the determinism test
    compares instead of two 400,000-element structures.
    """
    import hashlib

    digest = hashlib.sha256()
    for plan in plans:
        digest.update(plan.external_id.encode())
        digest.update(plan.student_class.encode())
        for event in plan.events:
            digest.update(
                f"{event.window}|{event.session_index}|{event.event_type}|"
                f"{event.skill_slot}|{event.offset_minutes}|{event.planted_for}|"
                f"{sorted(event.payload.items(), key=lambda kv: kv[0])}".encode()
            )
        for fact in plan.planted:
            digest.update(f"{fact.scenario}|{fact.skill_slot}|{fact.expected_status}".encode())
    return digest.hexdigest()


def _main() -> int:
    parser = argparse.ArgumentParser(description="Plan an E4 synthetic corpus (no database).")
    parser.add_argument("--students", type=int, default=CorpusConfig.students)
    parser.add_argument("--seed", type=int, default=CorpusConfig.seed)
    parser.add_argument("--manifest", type=pathlib.Path, default=None)
    args = parser.parse_args()

    config = CorpusConfig(students=args.students, seed=args.seed)
    plans = plan_corpus(config)
    events = sum(len(p.events) for p in plans)
    print(f"students={len(plans)} events={events} fingerprint={corpus_fingerprint(plans)[:16]}")
    by_class: dict[str, int] = {}
    for plan in plans:
        by_class[plan.student_class] = by_class.get(plan.student_class, 0) + 1
    print(f"classes={by_class}")
    if args.manifest:
        write_manifest(args.manifest, config, plans)
        print(f"manifest -> {args.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())


# `datetime`/`UTC` are re-exported for the benchmark runner's default corpus start.
DEFAULT_CORPUS_START = datetime(2026, 6, 1, tzinfo=UTC)
