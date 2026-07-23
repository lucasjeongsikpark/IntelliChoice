import type { ChildCandidate } from "../types";

interface Props {
  candidates: ChildCandidate[];
  onSelect: (studentId: string) => void;
  busy: boolean;
}

export function ChildSelectionScreen({ candidates, onSelect, busy }: Props) {
  return (
    <div className="panel">
      <h1>Who's learning today?</h1>
      <div className="card-list">
        {candidates.map((c) => (
          <button
            key={c.student_external_id}
            className="card"
            disabled={busy}
            onClick={() => onSelect(c.student_external_id)}
          >
            <strong>{c.display_name}</strong>
            <span>
              Grade {c.grade} · {c.branch_name}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
