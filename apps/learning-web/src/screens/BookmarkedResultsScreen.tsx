import { useEffect, useState } from "react";

import { getSessionResults } from "../api/client";
import { friendlyError } from "../api/errors";
import type { SessionResults } from "../types";
import { ResultsScreen } from "./ResultsScreen";

/**
 * `/results/:id` restored from a URL rather than from the live session (U4/D-338).
 *
 * **This is U4's fourth criterion, and the one D-327 could not meet.** `ResultsScreen` read the
 * session snapshot, so a `/results` route worked only while the graph still held that thread:
 * bookmark it, come back tomorrow, get a blank screen. `GET /learning/sessions/{id}/results` is
 * the endpoint that fixes that, and this is its only caller.
 *
 * **It renders the same `ResultsScreen`, deliberately.** The endpoint returns the whole
 * `learning_gain` object rather than a flattened subset, so there is no "restored from a URL"
 * variant of the screen to drift from the live one. A student cannot tell which path they took.
 */
interface Props {
  token: string;
  learningSessionId: string;
  onDone: () => void;
  onViewDashboard: () => void;
}

export function BookmarkedResultsScreen({
  token,
  learningSessionId,
  onDone,
  onViewDashboard,
}: Props) {
  const [results, setResults] = useState<SessionResults | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setResults(null);
    setError(null);
    getSessionResults(token, learningSessionId)
      .then((r) => {
        if (!cancelled) setResults(r);
      })
      .catch((e) => {
        // A 404 here is the ordinary case, not a fault: the session may still be in progress, may
        // belong to someone else, or may predate the results endpoint. The message says what the
        // student can do rather than what the server returned.
        if (!cancelled) setError(friendlyError(e));
      });
    return () => {
      cancelled = true;
    };
  }, [token, learningSessionId]);

  if (error !== null) {
    return (
      <div className="panel">
        <h2>These results aren&apos;t available</h2>
        <p className="dim">{error}</p>
        <button onClick={onDone}>Back to start</button>
        <button className="secondary" onClick={onViewDashboard}>
          View progress dashboard
        </button>
      </div>
    );
  }

  if (results === null) {
    return (
      <div className="panel">
        <p className="dim">Loading your results…</p>
      </div>
    );
  }

  return (
    <ResultsScreen
      gain={results.learning_gain}
      hintCount={results.hint_count}
      solutionCount={results.solution_count}
      videoCount={results.video_count}
      onDone={onDone}
      onViewDashboard={onViewDashboard}
    />
  );
}
