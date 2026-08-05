import type { TopicOption } from "../types";

interface Props {
  // D-187: `null` means "not loaded yet", which is not the same as "no topics" - an empty
  // list would be a real (and alarming) answer, so the two must not share a representation.
  topics: TopicOption[] | null;
  // Distinguishes "still loading" from "the fetch failed" - both leave `topics` null, and
  // showing the loading line for a failure is a spinner that never resolves.
  loadFailed: boolean;
  onSelect: (topicId: string) => void;
  busy: boolean;
  error: string | null;
}

export function TopicSelectScreen({ topics, loadFailed, onSelect, busy, error }: Props) {
  return (
    <div className="panel">
      <h1>Choose a topic</h1>
      {error && <p className="error">{error}</p>}
      {topics === null ? (
        loadFailed ? (
          <p className="error">We couldn&rsquo;t load the topics just now. Please refresh to try again.</p>
        ) : (
          <p>Loading topics…</p>
        )
      ) : (
        <div className="card-list">
          {topics.map((t) => (
            <button
              key={t.topic_id}
              className="card"
              disabled={busy || !t.available}
              onClick={() => onSelect(t.topic_id)}
            >
              <strong>{t.name}</strong>
              {/* Availability comes from the bank now, so "Coming soon" is a fact about
                  content rather than a flag someone remembered to flip. */}
              {!t.available && <span>Coming soon</span>}
              {t.recommended_for_grade && <span>Suggested for your grade</span>}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
