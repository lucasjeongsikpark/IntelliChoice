import { useCallback, useEffect, useState } from "react";

/**
 * AUD-F-04: the state that decides whether a stage narrative shows, kept across a refresh.
 *
 * `App.tsx` held both pieces in React state, so a reload re-opened a gate the student had
 * already closed and the narrative came back (`"Welcome back! Let's see what you remember
 * today."`). One further click clears it, which is the whole of why that finding was P3 -
 * but SPEC Phase 11's "done when" is that a refresh restores the student's exact position,
 * and landing on a narrative screen instead of the question is a different position.
 *
 * **The finding names one door and there are two.** `dismissedNarrative` is the explicit
 * one. `interactedPhase` (AUD-F-21) is the other: once the student has answered, skipped or
 * flagged something in this phase, a late-arriving narrative is dropped rather than shown.
 * That is also React state, so after a reload it was `null` again and a narrative the
 * student had already worked past would re-appear without ever having been "dismissed".
 * Persisting only the field the finding mentions would have left the defect reproducible
 * through the other path, which is why both live here.
 *
 * **Why `sessionStorage`.** It matches what this state means - scoped to one tab, gone when
 * the tab closes - and it is where `useLearningSession` already keeps the session id for the
 * same refresh-survival reason. `localStorage` would carry a dismissal into a new tab, where
 * a fresh session's first narrative should certainly show.
 *
 * **Why the record is keyed by learning session id, and why that is not optional.**
 * Dismissal is keyed by narrative *text* (S26's design, so a genuinely new narrative shows
 * again even after an earlier one was dismissed). Text alone stops being a safe key the
 * moment it is persisted: the welcome narrative is frequently *identical* across sessions,
 * so a student who dismissed it, ended the session and started another in the same tab would
 * have the new session's welcome narrative arrive pre-dismissed. Storing the session id
 * alongside makes the record self-invalidating - a mismatch reads as "no dismissal" without
 * anything having to remember to clear it.
 */

const STORAGE_KEY = "intellichoice.narrativeGate";

interface NarrativeGateRecord {
  learningSessionId: string;
  dismissedNarrative: string | null;
  interactedPhase: string | null;
}

function isRecord(value: unknown): value is NarrativeGateRecord {
  if (typeof value !== "object" || value === null) return false;
  const v = value as Record<string, unknown>;
  return (
    typeof v.learningSessionId === "string" &&
    (typeof v.dismissedNarrative === "string" || v.dismissedNarrative === null) &&
    (typeof v.interactedPhase === "string" || v.interactedPhase === null)
  );
}

/**
 * Every access is guarded. `sessionStorage` throws rather than returning null in a Safari
 * private window and when a quota is exceeded, and this is decoration on a screen the
 * student can always click past - it must never be the reason the app fails to render.
 * A malformed or foreign value is treated as absent for the same reason.
 */
function readRecord(): NarrativeGateRecord | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (raw === null) return null;
    const parsed: unknown = JSON.parse(raw);
    return isRecord(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

export interface NarrativeGate {
  /** The narrative text the student dismissed in *this* learning session, if any. */
  dismissedNarrative: string | null;
  /** The phase the student has already acted in, if any (AUD-F-21's rule). */
  interactedPhase: string | null;
  dismissNarrative: (narrative: string) => void;
  markInteracted: (phase: string) => void;
  /** Called when a session ends, so the next one in this tab starts with both gates open. */
  reset: () => void;
}

export function useNarrativeGate(learningSessionId: string | null): NarrativeGate {
  const [record, setRecord] = useState<NarrativeGateRecord | null>(readRecord);

  // State is the source of truth and the effect mirrors it to storage, rather than writing
  // inside the updaters: React may invoke an updater twice in StrictMode, and a reducer that
  // touches `sessionStorage` is not the pure function React is entitled to assume it is.
  useEffect(() => {
    try {
      if (record === null) sessionStorage.removeItem(STORAGE_KEY);
      else sessionStorage.setItem(STORAGE_KEY, JSON.stringify(record));
    } catch {
      // Non-fatal by design - see readRecord's note.
    }
  }, [record]);

  // Derived, not synchronised. A persisted record belonging to a different learning session
  // is simply not visible, so there is no effect that has to notice the change and no window
  // in which a stale dismissal is briefly live. It also means the very first render - where
  // `learningSessionId` is still null because no snapshot has arrived - correctly reports
  // both gates open.
  const active = record !== null && record.learningSessionId === learningSessionId ? record : null;

  const update = useCallback(
    (patch: Partial<Omit<NarrativeGateRecord, "learningSessionId">>) => {
      if (learningSessionId === null) return;
      setRecord((prev) => {
        const base: NarrativeGateRecord =
          prev !== null && prev.learningSessionId === learningSessionId
            ? prev
            : { learningSessionId, dismissedNarrative: null, interactedPhase: null };
        return { ...base, ...patch };
      });
    },
    [learningSessionId],
  );

  const dismissNarrative = useCallback(
    (narrative: string) => update({ dismissedNarrative: narrative }),
    [update],
  );
  const markInteracted = useCallback((phase: string) => update({ interactedPhase: phase }), [update]);
  const reset = useCallback(() => setRecord(null), []);

  return {
    dismissedNarrative: active?.dismissedNarrative ?? null,
    interactedPhase: active?.interactedPhase ?? null,
    dismissNarrative,
    markInteracted,
    reset,
  };
}
