"""D-329: every Bedrock task a background scheduler invokes must be in the gateway it is given.

**The bug this exists to prevent ran in production for as long as the feature had existed, and
its only symptom was a log line.** `_narrative_gateway` was written for `STAGE_NARRATIVE` and
later handed to `BackgroundHintPersonalizationScheduler` too — correct reuse, since the two are
the same shape of background call. The registry never grew to match, so every personalized hint
raised `no Bedrock model configured for task hint_personalization` inside the scheduler, was
swallowed exactly as background-task failures are meant to be, and the student silently received
the generic authored hint. **Measured on staging: 117 failures in 48 hours** — the only ERROR the
learning API was emitting at all.

**Why no existing test caught it.** The unit tests give the scheduler a stub gateway, so they
exercise the scheduler's logic and never the wiring. The e2e walks hit the real one, but a
personalized hint is *deliberately* indistinguishable from the canonical hint when it fails —
that is the fallback working as designed. A defect whose entire surface is "the good version
silently never happens" needs a test aimed at the wiring itself, which is what this is.

The generalizable form: **a registry keyed by task, compared against the tasks that are actually
called.** Any future scheduler added to this gateway fails here until its task is registered.
"""

from intellichoice_shared.bedrock import BedrockTask
from learning_api.main import _BACKGROUND_TUTOR_TASKS


def test_the_background_gateway_registers_stage_narrative() -> None:
    """D-217's original reason for this gateway."""
    assert BedrockTask.STAGE_NARRATIVE in _BACKGROUND_TUTOR_TASKS


def test_the_background_gateway_registers_hint_personalization() -> None:
    """**The regression test proper.** `BackgroundHintPersonalizationScheduler` is constructed
    with `gateway_factory=_narrative_gateway` in `main.py`'s lifespan, and calls
    `tutor.generate_personalized_hint`, which asks the gateway for
    `BedrockTask.HINT_PERSONALIZATION`. Without this entry that call raises, the scheduler
    swallows it, and the student gets the canonical hint forever."""
    assert BedrockTask.HINT_PERSONALIZATION in _BACKGROUND_TUTOR_TASKS


def test_every_registered_task_is_a_real_bedrock_task() -> None:
    """Cheap guard against a typo'd or removed enum member silently registering nothing - the
    dict comprehension in `_narrative_gateway` would happily build a registry keyed by a string
    that no caller ever asks for, which fails the same silent way."""
    for task in _BACKGROUND_TUTOR_TASKS:
        assert isinstance(task, BedrockTask)


def test_the_registry_has_no_duplicates() -> None:
    """A tuple rather than a set is used so the order stays readable, which means duplicates are
    possible; a duplicate would be harmless today but is a sign the list was edited carelessly."""
    assert len(_BACKGROUND_TUTOR_TASKS) == len(set(_BACKGROUND_TUTOR_TASKS))
