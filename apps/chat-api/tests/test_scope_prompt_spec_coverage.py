"""Static coverage guard for the scope-classification prompt (AUD-C-02).

SPEC §5.19.4 lists eight supported topics; the SCOPE_AND_INTENT system prompt
shipped without the first ("IntelliChoice organization") and fourth ("Student
participation"), so real Bedrock refused "What is IntelliChoice?" as out of
scope. No mock-backed test can see that class of omission: MockBedrockProvider
routes on its own keyword list, which contains "intellichoice", so every
organization question scores in-scope under the mock regardless of the prompt.
Asserting the prompt string itself is the only guard CI can enforce; behaviour
is verified separately by the CHAT_EVAL_REAL_BEDROCK coverage run.
"""

from chat_api.graph.nodes import (
    SCOPE_AND_INTENT_SYSTEM_PROMPT,
    UNAVAILABLE_INTENT_MESSAGES,
)

# SPEC §5.19.4 topic -> phrase the prompt must contain to claim coverage.
SPEC_5_19_4_TOPICS = {
    "IntelliChoice organization": "the intellichoice organization",
    "Branches": "branches",
    "Volunteering": "volunteering",
    "Student participation": "student participation",
    "Parent information": "parent information",
    "Tutor procedures": "tutor",
    "Academic calendar": "academic calendar",
    "Learning application support": "learning-app support",
}


def test_scope_prompt_covers_spec_topics() -> None:
    prompt = SCOPE_AND_INTENT_SYSTEM_PROMPT.lower()
    missing = [
        topic for topic, phrase in SPEC_5_19_4_TOPICS.items() if phrase not in prompt
    ]
    assert not missing, (
        f"SCOPE_AND_INTENT_SYSTEM_PROMPT omits SPEC §5.19.4 topics: {missing}"
    )


def test_clarification_message_names_the_organization() -> None:
    message = UNAVAILABLE_INTENT_MESSAGES["clarification"].lower()
    assert "intellichoice organization" in message
    assert "student participation" in message


# AUD-F-19 / AUD-C-02 verification leg: each phrase pins a live-measured misroute on
# real Bedrock (see the prompt's own comment). Same reasoning as the topic test above -
# the mock routes on its own keyword gate, so only the prompt string is CI-checkable;
# behaviour belongs to the CHAT_EVAL_REAL_BEDROCK paraphrase run.
INTENT_DEFINITION_PHRASES = {
    "branch_locator is location-scoped": "distance from the user's own location",
    "hours/schedule questions are document_qa": "hours, schedule, address",
    "admin_contact needs an explicit ask": "only an explicit request",
    "organization example pinned": "'what is intellichoice?' -> in_scope, document_qa",
    "people example pinned": (
        "'tell me about the people who run intellichoice' -> in_scope, document_qa"
    ),
    "hours example pinned": "'what are the saturday hours?' -> in_scope, document_qa",
}


def test_scope_prompt_defines_intents() -> None:
    prompt = SCOPE_AND_INTENT_SYSTEM_PROMPT.lower()
    missing = [
        label for label, phrase in INTENT_DEFINITION_PHRASES.items() if phrase not in prompt
    ]
    assert not missing, (
        f"SCOPE_AND_INTENT_SYSTEM_PROMPT lost intent definitions: {missing}"
    )
