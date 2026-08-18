"""Human verdicts on judge findings, so a recurring audit reports what is *new* (D-236).

D-235 adjudicated 25 disagreements between the declared tier of an item and the tier the
§5.8.5 judge gave it: 13 were the judge being right and 12 were the judge being wrong. The
13 were fixed by re-tiering. Nothing recorded the 12.

Without that record the audit is a one-shot. Re-run `audit_authored_bank.py --judge`
tomorrow and it re-reports the same 12 findings in the same words, indistinguishable from
twelve new ones, so either a human re-adjudicates decisions already made or - much more
likely, and much worse - learns that the flagged list is mostly noise and stops reading it.
An audit whose output is not trusted is an audit that has stopped working.

**A verdict is not inherited by an instrument that has changed** - but only the verdicts that
were about the instrument in the first place. The fingerprint's scope depends on what the
verdict claims (D-237, and see `fingerprint` for how running the tier-5 change exposed it):

- `upheld` says *the judge is wrong about this item*, so it hashes the item's judge payload,
  its topic's `difficulty_anchors`, **and the judge system prompt**. Change the prompt and it
  lapses, correctly - that claim is about a specific instrument.
- `retiered` says *this item's tier should be X by its anchors*, which is a human reading of
  content against a rubric. Prompt excluded: it is not an input, and must not be able to
  invalidate one.

The first version hashed the prompt into everything, and shipping one prompt sentence lapsed
all 28 records at once - 16 of them for a reason with no bearing on what they said. **Over-
hashing is not the safe direction.** It produces routine mass lapses, and a lapse that
happens for no reason is one people learn to clear without reading, which is how a record
stops being read at all.

So lapsing is expected but must be *earned*, and the reporting is built for it: a lapsed
record is printed with its reason rather than dropped, because "12 verdicts lapsed: the judge
prompt changed" is information, and silence is not.

**What that lapse then obliges.** D-237's re-run of exactly the 12 lapsed verdicts found 8
had become moot - the instrument now agreed - so those entries were deleted rather than
carried, and 4 were re-affirmed against the new prompt. A fingerprint refreshed without
re-deciding would have re-asserted twelve judgements nobody made, eight of them wrong.
"""

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml
from intellichoice_shared.bedrock import QuestionJudgePayload
from pydantic import BaseModel, ConfigDict

from intellichoice_curriculum.authored_bank import AuthoredTemplateDef
from intellichoice_curriculum.content import DEFAULT_CONTENT_ROOT, load_curriculum

DEFAULT_ADJUDICATIONS_PATH = DEFAULT_CONTENT_ROOT / "adjudications.yaml"

# What a verdict can say. `upheld` is the only one that suppresses anything - it means a
# human read the item against its anchors and decided the judge is wrong, so a repeat of
# that disagreement carries no new information. `retiered` deliberately suppresses nothing:
# the item was changed to match the judge, so it is now *expected* to agree, and a
# disagreement is news rather than a repeat.
Decision = Literal["upheld", "retiered"]


class Adjudication(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_template_id: str
    decision: Decision
    decided_on: str
    decided_in: str
    # The tier the item carried when the verdict was reached. Held separately from the
    # fingerprint so a re-tier can be reported as "the tier moved" rather than as the
    # generic "something changed" every other edit produces.
    declared_difficulty: int
    # What the judge said, and in which run. Historical by nature: for `place_value` and
    # `fraction_operations` this was measured in D-234 under the anchors D-235 then
    # tightened, so it records what prompted the verdict, not a current prediction.
    judge_difficulty: int | None = None
    measured_in: str | None = None
    fingerprint: str
    rationale: str


class AdjudicationFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int
    adjudications: list[Adjudication]


def fingerprint(
    payload: QuestionJudgePayload,
    anchors: dict[int, str],
    system_prompt: str | None = None,
) -> str:
    """What a verdict depends on, hashed - and the scope differs by what the verdict claims.

    **D-237 corrected this, and running the tier-5 change is what exposed it.** The first
    version hashed the judge prompt into every verdict, so changing one sentence in the
    prompt lapsed all 28 - including 16 the prompt has no bearing on:

    - `upheld` says *the judge is wrong about this item*. That is a claim about the item, its
      anchors **and the instrument**, so all three are hashed and a prompt change lapses it.
      This half was right, and it is why the tier-5 sentence correctly invalidated 12.
    - `retiered` says *this item's tier should be X by its anchors*. That is a human reading
      of content against a rubric. The judge prompt is not an input to it and must not be
      able to invalidate it, or the record churns for reasons unrelated to its content.

    The general rule this is an instance of: **hash what the claim actually depends on.**
    Over-hashing is not the safe direction - it produces routine mass lapses, and a lapse that
    happens for no reason is one people learn to clear without reading.

    Pydantic serializes in field-declaration order, so this is stable across runs without
    needing a sort; adding a field to `QuestionJudgePayload` changes every fingerprint, which
    is the correct outcome - the judge would be reading something new.
    """
    digest = hashlib.sha256()
    digest.update(payload.model_dump_json().encode())
    digest.update(b"\x00")
    digest.update(repr(sorted(anchors.items())).encode())
    if system_prompt is not None:
        digest.update(b"\x00")
        digest.update(system_prompt.encode())
    return digest.hexdigest()[:16]


def judge_inputs(
    item: AuthoredTemplateDef,
) -> tuple[QuestionJudgePayload, dict[int, str], str]:
    """Exactly what the blind judge is given for one item.

    Lives here rather than in the audit script because the fingerprint above is only
    meaningful if it hashes the *same* thing the judge is sent. Assembled in two places,
    they drift, and the failure is silent in the worst direction: a verdict goes on
    suppressing a finding about content the judge no longer reads.
    """
    from intellichoice_curriculum.ai_pipeline import judge_system_prompt

    curriculum = load_curriculum()
    topics = {t.topic_id: t for t in curriculum.topics}
    skills = {s.skill_id: s for s in curriculum.skills}
    topic = topics[item.topic_id]
    payload = QuestionJudgePayload(
        rendered_question=item.rendered_for_model(),
        option_a=item.option_a,
        option_b=item.option_b,
        option_c=item.option_c,
        option_d=item.option_d,
        correct_option=item.correct_option,
        hint_ladder=list(item.hint_ladder),
        canonical_solution=str(item.canonical_solution["final_answer"]),
        topic_name=topic.name,
        skill_name=skills[item.skill_id].name,
        grade_band=topic.grade_band,
    )
    return payload, topic.difficulty_anchors, judge_system_prompt(topic)


def load_adjudications(path: Path | None = None) -> dict[str, Adjudication]:
    """question_template_id -> verdict. A missing file is empty, not an error.

    Empty is the state every environment was in before D-236 and the state a fresh topic is
    in, so it must stay ordinary: the audit runs, reports everything as new, and says so.
    """
    source = path or DEFAULT_ADJUDICATIONS_PATH
    if not source.is_file():
        return {}
    parsed = AdjudicationFile.model_validate(yaml.safe_load(source.read_text()))
    by_id: dict[str, Adjudication] = {}
    for entry in parsed.adjudications:
        if entry.question_template_id in by_id:
            raise ValueError(
                f"{source}: two adjudications for {entry.question_template_id} - a second "
                f"verdict must replace the first, not sit beside it"
            )
        by_id[entry.question_template_id] = entry
    return by_id


# How a flagged item relates to the record. Only `known` suppresses.
Status = Literal["new", "known", "lapsed_tier", "lapsed_content", "moot"]


def classify(
    *,
    adjudication: Adjudication | None,
    declared_difficulty: int,
    current_fingerprint: str,
    disagrees: bool,
) -> Status:
    """Where one judged item belongs in the audit's report.

    `moot` is the case that is easy to leave out and worth keeping: an item adjudicated
    `upheld` that the judge now *agrees* with. Nothing is wrong with the item, so there is
    nothing to flag - but the instrument moved, and that is exactly what the tier-5 work is
    trying to find out. Reporting it as "the record is no longer needed" is how a suppressed
    finding coming back to life stays visible instead of just going quiet.
    """
    if adjudication is None:
        return "new"
    if adjudication.declared_difficulty != declared_difficulty:
        return "lapsed_tier"
    if adjudication.fingerprint != current_fingerprint:
        return "lapsed_content"
    if adjudication.decision == "retiered":
        # Changed to match the judge, so it is expected to agree now. A remaining
        # disagreement is a finding in its own right, not a repeat of the old one.
        return "new"
    return "known" if disagrees else "moot"


LAPSE_REASON: dict[Status, str] = {
    "lapsed_tier": "the item's declared tier changed since the verdict",
    "lapsed_content": "the item, its topic's anchors, or the judge prompt changed",
}


@dataclass(frozen=True)
class JudgedItem:
    """One judge result, reduced to what deciding-what-to-report depends on."""

    question_template_id: str
    declared_difficulty: int
    reviewed_difficulty: int
    flagged: bool
    # Two scopes, because two kinds of verdict depend on different things (D-237).
    content_fingerprint: str
    instrument_fingerprint: str


@dataclass
class Findings:
    """A judge run split by what a human has already ruled on.

    `new` is the only bucket that asks for attention. The others are printed anyway - a
    suppression that is never shown is indistinguishable from a bug in the suppression.
    """

    new: list[JudgedItem] = field(default_factory=list)
    known: list[JudgedItem] = field(default_factory=list)
    lapsed: list[JudgedItem] = field(default_factory=list)
    moot: list[JudgedItem] = field(default_factory=list)
    status: dict[str, Status] = field(default_factory=dict)


def partition_findings(items: list[JudgedItem], verdicts: dict[str, Adjudication]) -> Findings:
    """Split a judge run into new / known / lapsed / moot.

    Pure and separate from the audit script on purpose. This is the code that decides what
    a human never sees, and the judge task has no mock-provider branch - so run end to end
    it can only be exercised by paying, which is the worst possible property for a
    suppression rule to have.
    """
    findings = Findings()
    for item in items:
        verdict = verdicts.get(item.question_template_id)
        status = classify(
            adjudication=verdict,
            declared_difficulty=item.declared_difficulty,
            current_fingerprint=(
                item.content_fingerprint
                if verdict is not None and verdict.decision == "retiered"
                else item.instrument_fingerprint
            ),
            disagrees=item.flagged,
        )
        findings.status[item.question_template_id] = status
        if status == "moot":
            findings.moot.append(item)
        elif not item.flagged:
            continue
        elif status == "new":
            findings.new.append(item)
        elif status == "known":
            findings.known.append(item)
        else:
            findings.lapsed.append(item)
    return findings
