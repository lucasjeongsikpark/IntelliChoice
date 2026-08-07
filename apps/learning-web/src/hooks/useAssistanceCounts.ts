import { useCallback, useEffect, useState } from "react";

/**
 * How much help the student took this session, kept across a refresh.
 *
 * Found on staging 2026-08-07 by walking the deployed app: these three numbers were plain
 * React state in `App.tsx` (`useState({ hint: 0, solution: 0, video: 0 })`), so a page
 * refresh mid-session silently reset them to zero. The end-of-session results screen then
 * reported **1 hint, 0 solutions, 0 videos** for a session whose real usage was 2, 1 and 1 -
 * and the study-phase outro narrative on the *same* session said 2/1/1, because that one is
 * computed server-side from `study_attempts`. Two counters for one fact, disagreeing in front
 * of the student.
 *
 * It is not only cosmetic. "Solved independently" is the headline of the results screen, the
 * same counts feed the parent report, and under-reporting help taken makes a session look
 * better than it was. That is the same family as AUD-L-14's "0.0 minutes next to 26 attempts".
 *
 * **Why persist rather than read the server.** The server has the truth, but it is not on the
 * snapshot: `LearningGainResponse` carries `hint_dependency`/`solution_dependency` as *rates*,
 * not counts, and the study-outro narrative computes its numbers inside a graph node without
 * putting them on the wire. Surfacing them properly means widening the gain payload, which is
 * a bigger change than the defect warrants and touches the persisted gain row. Mirroring
 * `useNarrativeGate` (AUD-F-04) keeps the fix the size of the bug and uses the pattern this
 * codebase already reaches for when React state needs to survive a reload.
 *
 * Keyed by learning session id for the same reason the narrative gate is: a record from a
 * previous session in the same tab is simply not visible, so nothing has to remember to clear
 * it, and there is no window where the last session's counts are briefly live.
 */

const STORAGE_KEY = "intellichoice.assistanceCounts";

export type AssistanceKind = "hint" | "solution" | "video";

interface AssistanceCountsRecord {
  learningSessionId: string;
  hint: number;
  solution: number;
  video: number;
}

const ZERO = { hint: 0, solution: 0, video: 0 } as const;

function isRecord(value: unknown): value is AssistanceCountsRecord {
  if (typeof value !== "object" || value === null) return false;
  const v = value as Record<string, unknown>;
  return (
    typeof v.learningSessionId === "string" &&
    typeof v.hint === "number" &&
    typeof v.solution === "number" &&
    typeof v.video === "number"
  );
}

/** Guarded like `useNarrativeGate`'s: storage throws in a Safari private window and on a
 *  quota error, and a counter must never be the reason the results screen fails to render. */
function readRecord(): AssistanceCountsRecord | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (raw === null) return null;
    const parsed: unknown = JSON.parse(raw);
    return isRecord(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

export interface AssistanceCounts {
  counts: { hint: number; solution: number; video: number };
  record: (kind: AssistanceKind) => void;
  reset: () => void;
}

export function useAssistanceCounts(learningSessionId: string | null): AssistanceCounts {
  const [stored, setStored] = useState<AssistanceCountsRecord | null>(readRecord);

  // State is the source of truth, the effect mirrors it - StrictMode may invoke an updater
  // twice, and one that writes to storage is not the pure function React assumes.
  useEffect(() => {
    try {
      if (stored === null) sessionStorage.removeItem(STORAGE_KEY);
      else sessionStorage.setItem(STORAGE_KEY, JSON.stringify(stored));
    } catch {
      // Non-fatal by design - see readRecord.
    }
  }, [stored]);

  const active = stored !== null && stored.learningSessionId === learningSessionId ? stored : null;

  const record = useCallback(
    (kind: AssistanceKind) => {
      if (learningSessionId === null) return;
      setStored((prev) => {
        const base: AssistanceCountsRecord =
          prev !== null && prev.learningSessionId === learningSessionId
            ? prev
            : { learningSessionId, ...ZERO };
        return { ...base, [kind]: base[kind] + 1 };
      });
    },
    [learningSessionId],
  );

  const reset = useCallback(() => setStored(null), []);

  return {
    counts: active === null ? { ...ZERO } : { hint: active.hint, solution: active.solution, video: active.video },
    record,
    reset,
  };
}
