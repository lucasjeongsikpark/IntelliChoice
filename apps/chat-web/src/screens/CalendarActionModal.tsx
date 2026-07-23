import type { CalendarActionInterrupt } from "../types";

interface Props {
  pending: CalendarActionInterrupt;
  busy: boolean;
  onChoose: (choice: "google" | "ics" | "cancel") => void;
}

function formatDateTime(value: unknown): string {
  if (typeof value !== "string") return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

export function CalendarActionModal({ pending, busy, onChoose }: Props) {
  const event = pending.calendar_event ?? {};
  const title = typeof event.title === "string" ? event.title : "Event";
  const location = typeof event.location === "string" ? event.location : null;
  const description = typeof event.description === "string" ? event.description : "";

  return (
    <div className="modal-overlay">
      <div className="modal">
        <h2>Add to your calendar?</h2>
        <div className="email-preview">
          <strong>{title}</strong>
          <p className="dim">
            {formatDateTime(event.start_datetime)} – {formatDateTime(event.end_datetime)}
            {event.timezone ? ` (${String(event.timezone)})` : ""}
          </p>
          {location && <p className="dim">Location: {location}</p>}
          {description && <p>{description}</p>}
        </div>
        <div className="modal-actions">
          <button className="secondary" disabled={busy} onClick={() => onChoose("cancel")}>
            Cancel
          </button>
          <button disabled={busy} onClick={() => onChoose("ics")}>
            Download .ics
          </button>
          <button disabled={busy} onClick={() => onChoose("google")}>
            Add to Google Calendar
          </button>
        </div>
      </div>
    </div>
  );
}
