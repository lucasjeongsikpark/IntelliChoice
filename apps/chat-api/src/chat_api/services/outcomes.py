"""Why a turn ended the way it did, as a code the client can branch on (D-351).

**The problem this fixes.** Every "I can't answer that" in this app was a hardcoded string
produced by whichever node happened to decide it, with no shared classification. A client
could not tell an out-of-scope refusal from a no-approved-source one from a Bedrock outage
except by inferring it from `escalation_recommended`, `citations.length` and `access_hint`
being non-null - three fields that happen to correlate rather than a stated reason. That
coupling is what made AUD-C-19 possible (three different causes wearing one message) and what
kept `ChatScreen` de-duplicating `answer` against `access_hint.message` by string comparison.

Two things follow from separating them, and both were the point:

1. **Internal classification stops leaking into user-facing prose.** `out_of_scope` is a
   classifier label; "I cannot answer unrelated general-purpose questions" is that label
   read aloud at a parent asking how to get a mistaken donation refunded. The code stays
   `OUT_OF_SCOPE`; the words the visitor reads are chosen separately.
2. **A wrong classification stops being a wrong disclosure.** `ACCESS_REQUIRED`'s copy is
   deliberately generic - see `ACCESS_REQUIRED_MESSAGE`.

Reasons are a closed set. `MessageResponse.reason` carries the code; `REASON_MESSAGES` carries
the words. Nothing here is ever proposed by a model.
"""

from enum import StrEnum


class TurnReason(StrEnum):
    """Why this turn produced what it produced. One value per *cause*, not per message.

    Ordered roughly from "the system worked" to "the system did not".
    """

    #: A grounded, citation-supported answer (SPEC §5.21.8). Also covers the deterministic
    #: successes - a calendar file, an event listing, a branch list - because from the
    #: caller's side those are answers too.
    ANSWER = "answer"
    #: The question is one this assistant supports and the corpus does not answer it. An
    #: escalation to a human is offered, because a human may know.
    NO_APPROVED_SOURCE = "no_approved_source"
    #: Approved sources exist and disagree, so answering would mean picking one (SPEC
    #: §5.21.8). Distinct from NO_APPROVED_SOURCE: the remedy is confirmation, not research.
    SOURCES_CONFLICT = "sources_conflict"
    #: Content matching the question exists behind a role the caller does not hold. See
    #: `ACCESS_REQUIRED_MESSAGE` for why the copy names no role and no document.
    ACCESS_REQUIRED = "access_required"
    #: Not a topic this assistant covers. Says so without characterising the question.
    OUT_OF_SCOPE = "out_of_scope"
    #: The turn cannot finish without a person - the escalation path, and the caps on it.
    HUMAN_ACTION_REQUIRED = "human_action_required"
    #: Refused by policy rather than by knowledge: a rate limit, a consent the caller
    #: declined. Nothing about the question is wrong and retrying may work.
    POLICY_RESTRICTED = "policy_restricted"
    #: Something on our side failed. Explicitly *not* a statement about the question
    #: (AUD-C-07/AUD-C-08: an outage used to be reported as "your question was off-topic").
    SYSTEM_ERROR = "system_error"
    #: The assistant needs something more from the caller before it can answer - a ZIP code,
    #: a branch name, which event.
    NEEDS_CLARIFICATION = "needs_clarification"
    #: D-402: the caller withdrew the question - they pressed Stop and the turn observed it at
    #: a checkpoint boundary. Deliberately last and outside the "worked -> did not work"
    #: ordering above, because it describes neither the system nor the question: nothing failed
    #: and nothing about the question was wrong. A `reason` rather than a parallel boolean
    #: because this is already the field a client branches on, and because a field added to
    #: `MessageResponse` alone would be *nulled* on every broadcast (D-058/AUD-C-14).
    CANCELLED = "cancelled"


# SPEC §5.19.4's supported-topic list, which the out-of-scope copy still states because
# telling someone what the assistant *does* cover is the actionable half of a refusal.
SUPPORTED_TOPICS_SENTENCE = (
    "I can help with IntelliChoice programs, branches, schedules, volunteering, "
    "student learning, parent information and tutor or branch procedures."
)

# **Deliberately names no role and no document.**
#
# The previous copy was one of four role-specific strings ("That's available to parents - log
# in with a parent account to see it"), chosen by `role_access.build_access_hint` from the
# access probe's per-audience scores. Two problems, one measured and one structural:
#
# - **Measured (D-351):** the probe fires for 1 of 8 questions a gated document answers, so
#   the specific-role promise is mostly not kept anyway - and AUD-C-25/D-179 recorded a live
#   case where it named `parent` for a question the *public* corpus answers.
# - **Structural:** naming the tier tells an unauthenticated caller that a document restricted
#   to that tier exists and mentions their terms. That is a small disclosure, but it is one the
#   caller did not have before asking, and it is made by a probe that runs *because* the
#   normal pipeline already declined to answer.
#
# Generic copy makes a wrong audience selection harmless: the worst case becomes "you were told
# to sign in and it would not have helped", instead of "you were told to sign in *as a branch
# manager*". `required_role` is still computed and logged - it is useful for measuring the
# probe - it simply no longer reaches the caller.
ACCESS_REQUIRED_MESSAGE = (
    "I can't answer that from the sources available to you. Some information is only "
    "available once you sign in, so signing in may help."
)

# The out-of-scope copy, and the one change here that departs from a SPEC-verbatim string.
#
# SPEC §5.19.4 ended "I cannot answer unrelated general-purpose questions." Measured live
# (D-343): a parent asking how to request a refund for a donation made by mistake is told
# their question is an unrelated general-purpose one. The *classification* is defensible -
# donations are not on §5.19.4's topic list, and D-351 deliberately does not add them - but
# describing an organization-adjacent question that way is the classifier label read aloud.
#
# The replacement keeps the actionable half (what this assistant does cover), drops the
# characterisation, and points at a human. SPEC §5.19.4 is updated to match rather than left
# to disagree with the code.
OUT_OF_SCOPE_MESSAGE = (
    f"{SUPPORTED_TOPICS_SENTENCE}\n"
    "I can't help with that topic through this assistant. For anything else, your branch "
    "can point you to the right person."
)

NO_APPROVED_SOURCE_MESSAGE = (
    "I don't have an approved source for that yet. I can pass this on to a branch "
    "manager if you'd like."
)

SOURCES_CONFLICT_MESSAGE = (
    "The documents I found disagree with each other on this, so I don't want to guess. "
    "I can pass this on to a branch manager to confirm."
)

SYSTEM_ERROR_MESSAGE = (
    "I can't look that up right now - the assistant is temporarily unavailable.\n\n"
    "This is a problem on our side, not with your question. Please try again in a few "
    "minutes. If it keeps happening, contact your branch manager."
)

# The default copy for a reason, used where a node has nothing more specific to say. A node
# with a *more* specific message for the same reason (the calendar paths, the location paths)
# keeps it: the reason code is the contract, the exact words are not.
REASON_MESSAGES: dict[TurnReason, str] = {
    TurnReason.NO_APPROVED_SOURCE: NO_APPROVED_SOURCE_MESSAGE,
    TurnReason.SOURCES_CONFLICT: SOURCES_CONFLICT_MESSAGE,
    TurnReason.ACCESS_REQUIRED: ACCESS_REQUIRED_MESSAGE,
    TurnReason.OUT_OF_SCOPE: OUT_OF_SCOPE_MESSAGE,
    TurnReason.SYSTEM_ERROR: SYSTEM_ERROR_MESSAGE,
}

# Reasons where offering to forward the question to a human is the useful next step. Read by
# nothing yet - `escalation_recommended` still comes from the model for NO_APPROVED_SOURCE -
# but stated here so the two cannot drift apart silently, and so a reader can see which
# refusals are *supposed* to end in a person.
ESCALATABLE = frozenset(
    {TurnReason.NO_APPROVED_SOURCE, TurnReason.SOURCES_CONFLICT, TurnReason.OUT_OF_SCOPE}
)
