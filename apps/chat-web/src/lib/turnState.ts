/**
 * What state a transcript turn is in — one definition, read by everything that branches on it.
 *
 * **Why this is a module rather than a helper inside `ChatScreen`.** `isFinishedTurn` lived in
 * `ChatScreen.tsx` and the render gate was the only thing that knew the rule. `useChatSession` now
 * needs the same judgement (D-413's deadline has to know which replayed turns are still waiting),
 * and a second copy of a four-clause predicate in another file is how the screen and the hook end up
 * disagreeing about whether a turn is finished — the shape `mastery_policy.py` exists to prevent
 * (AUD-L-13/D-156) and the one D-408 refused to introduce in TypeScript.
 */

import type { ChatTurn, TurnSnapshot } from "../types";

/**
 * Whether a snapshot describes a turn that has **finished**, as opposed to one the server is
 * still working on (D-379).
 *
 * **The defect this closes.** `resolve_role` clears `answer`, `citations`, `reason` and the
 * rest at turn *start*, while `client_turn_id` is already in the checkpoint. `/stream` emits
 * its initial snapshot on every connect with no "is a turn running?" guard, so a reload two
 * seconds into a 6-11s question restored a turn whose response was present and empty. D-348's
 * matcher found the id, matched confidently, and committed it - and the bubble rendered *"No
 * answer came back for that one. Try asking it again."* Following that instruction produced a
 * 409, and seconds later the real answer overwrote the refusal.
 *
 * In a product where a refusal is a first-class outcome, that **fabricates one** and instructs
 * an action that fails.
 *
 * `reason` is the discriminator and it is server-authored: cleared to null on entry, and set
 * by every terminal node (`ANSWER`, `NO_APPROVED_SOURCE`, `OUT_OF_SCOPE`, `ACCESS_REQUIRED`,
 * `POLICY_RESTRICTED`, `NEEDS_CLARIFICATION`, `HUMAN_ACTION_REQUIRED`, `SYSTEM_ERROR`). So
 * `reason === null` means "not finished" rather than "finished with nothing to say".
 *
 * D-351 added that field describing it as *"the field a client should branch on"* and no
 * component read it. This is the first one.
 *
 * The fallbacks matter for old checkpoints: a session checkpointed before `reason` existed has
 * none, so anything else that renders is also accepted as evidence the turn completed.
 */
export function isFinishedTurn(response: TurnSnapshot): boolean {
  return (
    response.reason !== null ||
    Boolean(response.answer) ||
    Boolean(response.access_hint) ||
    response.citations.length > 0 ||
    response.escalation_recommended ||
    Boolean(response.pending_interrupt)
  );
}

/**
 * Whether this turn is still waiting on an answer — i.e. whether `Thinking…` is on screen for it.
 *
 * The three terminal markers (`error`, `cancelled`, `unresolved`) are all excluded, so anything
 * that has reached an end state is not pending no matter what its `response` looks like. That is
 * what lets `useChatSession`'s deadline use this predicate directly as its guard: a turn the
 * visitor stopped, or that already failed, can never be re-marked by it.
 */
export function isPendingTurn(turn: ChatTurn): boolean {
  if (turn.error || turn.cancelled || turn.unresolved) return false;
  return !turn.response || !isFinishedTurn(turn.response);
}
