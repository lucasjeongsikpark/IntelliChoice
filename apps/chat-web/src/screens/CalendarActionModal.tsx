import { ApprovalModal } from "../components/ApprovalModal";
import { formatEventDateTime } from "../lib/eventDateTime";
import type { CalendarActionInterrupt } from "../types";

interface Props {
  pending: CalendarActionInterrupt;
  busy: boolean;
  error?: string | null;
  onChoose: (choice: "google" | "ics" | "cancel") => void;
}

export function CalendarActionModal({ pending, busy, error, onChoose }: Props) {
  const event = pending.calendar_event ?? {};
  const title = typeof event.title === "string" ? event.title : "Event";
  const location = typeof event.location === "string" ? event.location : null;
  const description = typeof event.description === "string" ? event.description : "";
  // WORK-40-TZ: one zone, read once, used by both the rendered times and the suffix that names
  // them - the defect was those two disagreeing.
  const timezone = typeof event.timezone === "string" ? event.timezone : null;

  return (
    // Escape cancels: the other two buttons both act on the user's calendar (D-219).
    <ApprovalModal
      titleId="calendar-action-title"
      error={error}
      onDismiss={() => onChoose("cancel")}
    >
      <h2 id="calendar-action-title">Add to your calendar?</h2>
      <div className="email-preview">
        <strong>{title}</strong>
        <p className="dim">
          {formatEventDateTime(event.start_datetime, timezone)} –{" "}
          {formatEventDateTime(event.end_datetime, timezone)}
          {timezone ? ` (${timezone})` : ""}
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
    </ApprovalModal>
  );
}
