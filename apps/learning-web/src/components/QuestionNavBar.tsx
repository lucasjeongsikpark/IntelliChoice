import { useRef } from "react";
import type { ExamItemStatus } from "../types";

interface Props {
  items: ExamItemStatus[];
  currentDisplayOrder: number;
  disabled: boolean;
  onJump: (displayOrder: number) => void;
}

// Status is never signaled by color alone - each chip also carries a text glyph and a
// full aria-label, so the nav bar stays legible for colorblind and screen-reader users.
const STATUS_GLYPH: Record<ExamItemStatus["status"], string> = {
  unseen: "",
  answered: "✓",
  skipped: "–",
  flagged: "⚑",
};

const STATUS_LABEL: Record<ExamItemStatus["status"], string> = {
  unseen: "not yet answered",
  answered: "answered, locked",
  skipped: "skipped",
  flagged: "flagged for review",
};

// A toolbar-style roving-tabindex list (WAI-ARIA pattern): only the current/focused chip
// is a tab stop, arrow keys move focus between siblings, Home/End jump to the ends.
export function QuestionNavBar({ items, currentDisplayOrder, disabled, onJump }: Props) {
  const buttonRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const sorted = [...items].sort((a, b) => a.display_order - b.display_order);

  function focusIndex(index: number) {
    const clamped = Math.max(0, Math.min(sorted.length - 1, index));
    buttonRefs.current[clamped]?.focus();
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLButtonElement>, index: number) {
    switch (event.key) {
      case "ArrowRight":
      case "ArrowDown":
        event.preventDefault();
        focusIndex(index + 1);
        break;
      case "ArrowLeft":
      case "ArrowUp":
        event.preventDefault();
        focusIndex(index - 1);
        break;
      case "Home":
        event.preventDefault();
        focusIndex(0);
        break;
      case "End":
        event.preventDefault();
        focusIndex(sorted.length - 1);
        break;
    }
  }

  return (
    <nav className="exam-nav" aria-label="Question navigator">
      <ol className="exam-nav-list">
        {sorted.map((item, index) => {
          const isCurrent = item.display_order === currentDisplayOrder;
          return (
            <li key={item.assessment_item_id}>
              <button
                type="button"
                ref={(el) => {
                  buttonRefs.current[index] = el;
                }}
                className={`exam-nav-item status-${item.status}${isCurrent ? " current" : ""}`}
                tabIndex={isCurrent ? 0 : -1}
                aria-current={isCurrent ? "true" : undefined}
                aria-label={`Question ${item.display_order + 1}, ${STATUS_LABEL[item.status]}`}
                disabled={disabled}
                onClick={() => onJump(item.display_order)}
                onKeyDown={(event) => handleKeyDown(event, index)}
              >
                <span aria-hidden="true">{item.display_order + 1}</span>
                <span className="exam-nav-glyph" aria-hidden="true">
                  {STATUS_GLYPH[item.status]}
                </span>
              </button>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
