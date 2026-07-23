interface Props {
  narrative: string;
  evidence: string[];
  onContinue: () => void;
}

export function StageTransitionScreen({ narrative, evidence, onContinue }: Props) {
  return (
    <div className="panel">
      <div className="gradient-bar" aria-hidden="true" />
      <p className="subtitle">{narrative}</p>

      {evidence.length > 0 && (
        <details>
          <summary>How we personalized this</summary>
          <ul>
            {evidence.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </details>
      )}

      <button onClick={onContinue}>Continue</button>
    </div>
  );
}
