import { TOPICS } from "../topics";

interface Props {
  onSelect: (topicId: string) => void;
  busy: boolean;
  error: string | null;
}

export function TopicSelectScreen({ onSelect, busy, error }: Props) {
  return (
    <div className="panel">
      <h1>Choose a topic</h1>
      {error && <p className="error">{error}</p>}
      <div className="card-list">
        {TOPICS.map((t) => (
          <button
            key={t.id}
            className="card"
            disabled={busy || !t.available}
            onClick={() => onSelect(t.id)}
          >
            <strong>{t.label}</strong>
            {!t.available && <span>Coming soon</span>}
          </button>
        ))}
      </div>
    </div>
  );
}
