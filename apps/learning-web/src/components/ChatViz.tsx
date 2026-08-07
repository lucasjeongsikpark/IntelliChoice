import type { ChatViz as ChatVizData } from "../api/client";

/**
 * D-217: renders the tutor chat's optional bounded diagram (`ChatVizSpec` on the backend).
 *
 * A pure function of already-validated numbers and short strings - the values are bounded
 * to [-100, 100] and the labels to 24 chars by the schema the model filled, so this only
 * ever draws inside a fixed box and never interpolates model output into markup or a URL.
 * Two shapes: `bar_model` (labelled horizontal bars, the SkillFocus bar's idiom) and
 * `number_line` (a line with labelled marks). SVG text is rendered as text nodes by the
 * browser, so there is no injection surface, matching RichText's guarantee.
 */
export function ChatViz({ viz }: { viz: ChatVizData }) {
  return (
    <figure className="chat-viz">
      {viz.kind === "bar_model" ? <BarModel viz={viz} /> : <NumberLine viz={viz} />}
      <figcaption>{viz.caption}</figcaption>
    </figure>
  );
}

function BarModel({ viz }: { viz: ChatVizData }) {
  // Share one scale across the bars so their lengths are comparable. Guard a zero/negative
  // max so a degenerate spec still renders a (zero-width) bar rather than dividing by zero.
  const max = Math.max(1, ...viz.values.map((v) => Math.abs(v)));
  return (
    <div className="chat-viz-bars">
      {viz.labels.map((label, i) => {
        const value = viz.values[i] ?? 0;
        const pct = Math.max(0, (Math.abs(value) / max) * 100);
        return (
          <div key={i} className="chat-viz-bar-row">
            <span className="chat-viz-bar-label">{label}</span>
            <span className="chat-viz-bar-track">
              <span className="chat-viz-bar-fill" style={{ width: `${pct}%` }} />
            </span>
            <span className="chat-viz-bar-value">{formatValue(value)}</span>
          </div>
        );
      })}
    </div>
  );
}

function NumberLine({ viz }: { viz: ChatVizData }) {
  const min = Math.min(...viz.values);
  const max = Math.max(...viz.values);
  // Pad the ends so a mark at the extreme is not clipped, and avoid a zero-width span when
  // every value is equal.
  const span = max - min || 1;
  const lo = min - span * 0.15;
  const range = max + span * 0.15 - lo;
  const at = (v: number) => ((v - lo) / range) * 100;
  return (
    <div className="chat-viz-numberline">
      <span className="chat-viz-line" aria-hidden="true" />
      {viz.labels.map((label, i) => {
        const value = viz.values[i] ?? 0;
        return (
          <span key={i} className="chat-viz-mark" style={{ left: `${at(value)}%` }}>
            <span className="chat-viz-mark-dot" aria-hidden="true" />
            <span className="chat-viz-mark-label">
              {label} ({formatValue(value)})
            </span>
          </span>
        );
      })}
    </div>
  );
}

function formatValue(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(2).replace(/\.?0+$/, "");
}
