"""Base study plan, difficulty routing, and per-question serving (SPEC §5.11.1-§5.11.2).

Priority rules (§5.11.2), applied in order:
1. Lowest mastery skill - target skills are ranked by `Mastery.weighted_score` ascending.
   This outranks rule 2, so the *skill* is chosen by measured weakness and never moved by
   the difficulty recommendation (AUD-L-12's decision).
2. Difficulty matching estimated level - within the chosen skill, `_select_template` prefers
   an approved template whose `difficulty_label` equals `Mastery.recommended_difficulty`
   (the bootstrap model's step-up/hold/step-down output, §5.11.2 rules 2-3).
3. Difficulty within +/-1 - when no template sits exactly at the recommended tier,
   `_select_template` widens to +/-1 before falling back to the skill's whole approved pool,
   so a recommendation can narrow the choice but never empty it. Separately, the retry
   ladder's prerequisite step drops a skill line one tier via `curriculum.prerequisite_for`
   (see `flow._advance_study`).
4. Template not yet used this session - tracked via `used_template_ids`. Applied *within* the
   difficulty-filtered pool first, per SPEC's ranking of rules 2-3 above rule 4; but when that
   pool is exhausted rule 4 now **widens the tier instead of repeating a template** (D-325).

   **This is a deliberate departure from SPEC's stated ranking, and the reason is measured.**
   This module used to read "a used template at the recommended tier beats an unused one two
   tiers away", which is faithful to §5.11.2 and was wrong in practice: `used_template_ids` is
   seeded from the session's own *exam*, so "repeat a used template" meant handing the student
   the exact question they were about to be re-scored on. On the dev database **57 of 201 study
   items did exactly that, 40 of them at the very first study item** - not from a missing
   filter but because the recommended tier can hold as little as one template
   (`g4_mult_by_one_digit` at tier 1) and the exam takes it first. A recommendation is a
   preference, which `_closest_to_recommended`'s docstring already says; the learning gain a
   parent report is built on is not. One tier off is a worse question, the same question is a
   worse measurement, so the preference yields.
5. Same skill as recent error - implied by #1 (weakest skills are served first).
6. Prerequisite requirement - now honored: the 3rd-attempt remediation serves the skill's
   prerequisite (content-level, no Postgres table needed).
7. Not quarantined - already enforced by `get_active_questions_for_skill`'s
   active/approved filter.

Unlike S5's fixed 5-question batch, questions are now created one at a time so the retry
ladder can inject dynamic retry/prerequisite remediation items (SPEC §5.11.7); this module
owns the base-plan build plus the shared `create_study_item` used by both the plan and the
flow's ladder.
"""

import logging
import random

from intellichoice_curriculum.content import load_curriculum
from intellichoice_db.models.mastery import StudyItem, StudySession
from intellichoice_db.models.questions import QuestionTemplate
from intellichoice_db.repositories.mastery import MasteryRepository
from intellichoice_db.repositories.memory import MemoryRepository
from intellichoice_db.repositories.questions import QuestionRepository
from intellichoice_db.repositories.study import StudyRepository

from learning_api.services.study_outcomes import MAX_ATTEMPTS_PER_SKILL
from learning_api.services.variant_persistence import generate_and_store_variant

logger = logging.getLogger(__name__)

BASE_PROBLEM_COUNT = 5


class StudyPlanBuildError(Exception):
    """No approved templates exist for a skill the study plan needs to target."""


def _closest_to_recommended(
    candidates: list[QuestionTemplate], recommended_difficulty: int | None
) -> list[QuestionTemplate]:
    """Narrow `candidates` to the tier the bootstrap model recommends (§5.11.2 rule 2),
    widening to +/-1 (rule 3) and then to everything rather than ever returning empty -
    a recommendation is a preference, and a skill with no template near it must still be
    servable.

    **This used to say "provably inert on the current curriculum", and that is now false
    (D-341).** It was written when the bank was 5 skills x 10 templates at one tier each, so
    every branch returned the same full list and AUD-L-12 could hide. Measured 2026-08-15: the
    bank holds 958 items and **81 of 96 spanning skills carry approved templates at more than
    one tier**, so the exact-match and +/-1 branches now select genuinely different pools. The
    same docstring also claimed "there is no content that can exercise it", which is the
    opposite of true - `test_study_plan_difficulty_routing.py` now exercises it against the
    real curriculum rather than only against hand-built templates.

    **The final fallback is load-bearing and must stay** (D-341). 15 spanning skills declare
    tiers the bank does not yet stock - `adv_vectors` declares [2, 4, 5] and holds only tier 2 -
    and the user's decision is that those declarations stay, because the gaps close by
    generating content rather than by narrowing the taxonomy. So a recommendation of 4 or 5 for
    that skill lands outside +/-1 of anything approved, and `within_one or candidates` is what
    keeps the skill servable. Returning empty there would make a declared-but-unstocked tier a
    dead end.

    Order is preserved, so the `rng.choice` downstream stays deterministic (Phase 10).
    """
    if recommended_difficulty is None:
        return candidates
    exact = [t for t in candidates if t.difficulty_label == recommended_difficulty]
    if exact:
        return exact
    within_one = [t for t in candidates if abs(t.difficulty_label - recommended_difficulty) <= 1]
    return within_one or candidates


async def _select_template(
    question_repo: QuestionRepository,
    skill_id: str,
    used_template_ids: set[str],
    rng: random.Random,
    recommended_difficulty: int | None,
):
    """Pick an approved template for `skill_id`: closest to `recommended_difficulty`
    (§5.11.2 rules 2-3), then preferring one not yet used this session (rule 4).

    When the recommended tier holds nothing unused, this **widens the tier to find an unused
    template** rather than repeating one (D-325) - nearest tier first, so it stays as close to
    the recommendation as the bank allows. Only when every approved template for the skill has
    been used does it repeat, and that case is logged because by then the fix is content. See
    the module docstring's rule 4 for the measurement behind the departure from SPEC's
    ranking.

    `recommended_difficulty` is required rather than defaulted - a caller that does not
    want difficulty routing has to pass `None` and say why (the retry ladder does; see
    `flow._advance_study`). Defaulting it is how the value went unused in the first place.
    """
    candidates = await question_repo.get_active_questions_for_skill(skill_id)
    if not candidates:
        raise StudyPlanBuildError(f"no approved templates for skill {skill_id}")
    matched = _closest_to_recommended(candidates, recommended_difficulty)
    unused = [t for t in matched if t.question_template_id not in used_template_ids]
    if unused:
        return rng.choice(unused)

    # **The recommended tier is exhausted, so widen the tier rather than repeat a question
    # (D-325).** `pool = unused or matched` used to stop here and re-serve something already
    # used this session - which, because `used_template_ids` is seeded from the *exam's*
    # templates, meant serving the student the exact question they are about to be re-scored
    # on. Measured on the dev database: **57 of 201 study items repeated one of their own
    # session's exam templates, 40 of them at the first study item**, and the cause is pool
    # size rather than a missing filter. `_closest_to_recommended` returns only the *exact*
    # tier when one matches, and `g4_mult_by_one_digit` holds **one** approved template at tier
    # 1 while `time_read_clock` holds two - so once the exam has taken them, the exact tier has
    # nothing left and the old fallback had no choice but to repeat.
    #
    # Widening is the right thing to give up because §5.11.2's recommendation is explicitly a
    # *preference* - `_closest_to_recommended`'s own docstring says so - while practising the
    # question you are scored on inflates the learning gain the parent report is built from.
    # One tier off is a worse question; the same question is a worse *measurement*.
    unused_any_tier = [t for t in candidates if t.question_template_id not in used_template_ids]
    if unused_any_tier:
        # Nearest tier first, so this stays as close to the recommendation as the bank allows
        # rather than jumping to whatever is free. Ties keep candidate order, so `rng.choice`
        # below is still reproducible from the session seed (Phase 10).
        if recommended_difficulty is not None:
            unused_any_tier.sort(
                key=lambda t: abs(t.difficulty_label - recommended_difficulty)
            )
            nearest = abs(unused_any_tier[0].difficulty_label - recommended_difficulty)
            unused_any_tier = [
                t
                for t in unused_any_tier
                if abs(t.difficulty_label - recommended_difficulty) == nearest
            ]
        return rng.choice(unused_any_tier)

    # Every approved template for this skill has been used this session. Repeating is now the
    # only alternative to serving nothing, so it is still done - but it is logged, because the
    # honest fix at this point is content and nobody should have to re-derive that from a
    # student's transcript.
    logger.info(
        "study_template_repeat_unavoidable",
        extra={
            "skill_id": skill_id,
            "recommended_difficulty": recommended_difficulty,
            "approved_templates_for_skill": len(candidates),
            "already_used_this_session": len(used_template_ids),
        },
    )
    return rng.choice(matched)


async def create_study_item(
    *,
    question_repo: QuestionRepository,
    study_repo: StudyRepository,
    study_session_id: str,
    target_skill_id: str,
    skill_id: str,
    display_order: int,
    is_remediation: bool,
    used_template_ids: set[str],
    rng: random.Random,
    recommended_difficulty: int | None,
) -> StudyItem:
    """Generate one variant for `skill_id` and persist a `StudyItem` for it. `skill_id` is
    the question's actual skill (a prerequisite skill for prerequisite remediation);
    `target_skill_id` is the base skill whose line this item belongs to, so all attempts on
    a line - base and remediation - count toward the same skill's resolution.

    `recommended_difficulty` is `Mastery.recommended_difficulty` for the skill being served,
    or `None` to serve from the skill's whole approved pool (§5.11.2 rules 2-3; see
    `_select_template`).
    """
    template = await _select_template(
        question_repo, skill_id, used_template_ids, rng, recommended_difficulty
    )
    used_template_ids.add(template.question_template_id)
    variant_row = await generate_and_store_variant(
        question_repo=question_repo, template=template, rng=rng
    )
    return await study_repo.add_item(
        StudyItem(
            study_session_id=study_session_id,
            question_variant_id=variant_row.question_variant_id,
            display_order=display_order,
            target_skill_id=target_skill_id,
            skill_id=skill_id,
            difficulty=template.difficulty_label,
            is_remediation=is_remediation,
        )
    )


async def build_study_plan(
    *,
    question_repo: QuestionRepository,
    mastery_repo: MasteryRepository,
    study_repo: StudyRepository,
    student_external_id: str,
    topic_id: str,
    used_template_ids: set[str],
    rng: random.Random,
    memory_repo: MemoryRepository | None = None,
) -> StudySession:
    """Rank the topic's skills weakest-first (rule 1), record the plan, and serve the first
    base question. Remaining base skills and any remediation are served on demand by the
    flow as the student progresses.

    `memory_repo` (S25, plan §9) is optional so every existing caller/test keeps working
    unchanged - when passed, an `active` `weak_skill` semantic-memory fact for a skill
    breaks a `weighted_score` tie in that skill's favor. This only ever activates when
    two skills' measured mastery is exactly equal (most commonly: neither has a mastery
    row yet) - it never overrides a real mastery-score difference.
    """
    curriculum = load_curriculum()
    skills = curriculum.skills_for_topic(topic_id)
    if not skills:
        raise StudyPlanBuildError(f"topic {topic_id} has no skills defined")

    # D-288: only skills that can actually serve an item may be study targets. The ranking
    # below reads the *taxonomy's* skill list, and a taxonomy skill with zero bank items
    # has no mastery row, ties at 0.0, and wins selection precisely because nobody has
    # ever practised it - then `create_study_item` finds nothing and the student's exam
    # finalize dies with a 503. Measured live: the calculus band walk drew
    # `calc_differential_equations` (in the taxonomy, zero items) on some runs and not
    # others, because the target set depends on which questions were answered wrong.
    # Five topics carry such skills today; filtering here is what makes stocking a skill
    # a content decision rather than a serving outage.
    stocked = await question_repo.skill_ids_with_servable_items(
        [skill.skill_id for skill in skills]
    )
    skills = [skill for skill in skills if skill.skill_id in stocked]
    if not skills:
        # Fail closed exactly as before: a topic with no studyable content at all is a
        # real outage, not something to paper over with an empty plan.
        raise StudyPlanBuildError(f"topic {topic_id} has no skills with servable items")

    weak_skill_ids: set[str] = set()
    if memory_repo is not None:
        facts = await memory_repo.list_facts_for_student(student_external_id)
        weak_skill_ids = {
            fact.skill_id for fact in facts if fact.fact_type == "weak_skill" and fact.skill_id
        }

    ranked = []
    for position, skill in enumerate(skills):
        mastery = await mastery_repo.get_mastery(student_external_id, skill.skill_id)
        weighted = mastery.weighted_score if mastery is not None else 0.0
        recommended = mastery.recommended_difficulty if mastery is not None else None
        tie_break = 0 if skill.skill_id in weak_skill_ids else 1
        # Weakest weighted_score first; a `weak_skill` memory fact breaks a tie next;
        # curriculum order (position, ~difficulty asc) breaks any remaining tie, so
        # identical inputs always produce the same target ordering (Phase 10).
        ranked.append((weighted, tie_break, position, skill.skill_id, recommended))
    ranked.sort(key=lambda r: (r[0], r[1], r[2]))

    target = ranked[:BASE_PROBLEM_COUNT]
    target_skill_ids = [skill_id for _, _, _, skill_id, _ in target]
    # The first target's own recommendation, used for its starting question (§5.11.2 rule
    # 2). The remaining base skills are served later by `flow._serve_next_base_or_complete`,
    # which re-reads each one's mastery row at serve time rather than carrying these values
    # on the session - by then the row has been recomputed from the study attempts so far,
    # so a stale recommendation would be worse than a fresh read.
    first_recommended = target[0][4]

    study_session = await study_repo.create_study_session(
        StudySession(
            student_external_id=student_external_id,
            topic_id=topic_id,
            target_skill_ids=target_skill_ids,
            starting_difficulty=1,  # overwritten below with the first served item's tier
            base_problem_count=len(target_skill_ids),
            maximum_attempts_per_skill=MAX_ATTEMPTS_PER_SKILL,
            intervention_policy={"hints_enabled": True},
        )
    )

    first_item = await create_study_item(
        question_repo=question_repo,
        study_repo=study_repo,
        study_session_id=study_session.study_session_id,
        target_skill_id=target_skill_ids[0],
        skill_id=target_skill_ids[0],
        display_order=0,
        is_remediation=False,
        used_template_ids=used_template_ids,
        rng=rng,
        recommended_difficulty=first_recommended,
    )
    # The session is a tracked instance; mutating it here persists on the next flush
    # (`create_study_item` already flushed the item, and later attempt writes flush again).
    # `starting_difficulty` is the tier actually served, which `first_recommended` now
    # influences via `_select_template` - it is not assigned the recommendation directly,
    # because a recommendation with no template near it must not be recorded as if it had
    # been served (AUD-L-12).
    study_session.starting_difficulty = first_item.difficulty

    return study_session
