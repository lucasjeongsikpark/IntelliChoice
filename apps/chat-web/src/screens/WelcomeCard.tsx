import type { ChatMeta } from "../types";

interface Props {
  meta: ChatMeta | null;
  onPromptClick: (prompt: string) => void;
}

// SPEC §18-C3/plan §2.2, §2.5-UX: shown only while the transcript is empty (see
// `ChatScreen`'s own render) - a 2-line grounded welcome plus role-aware suggestion
// chips, so a new caller sees what the assistant can help with before typing anything.
export function WelcomeCard({ meta, onPromptClick }: Props) {
  if (!meta) return null;

  return (
    <div className="welcome-card">
      <p>{meta.welcome_text}</p>
      {meta.suggested_prompts.length > 0 && (
        <div className="suggestion-chips">
          {meta.suggested_prompts.map((prompt) => (
            <button
              key={prompt}
              className="chip"
              type="button"
              onClick={() => onPromptClick(prompt)}
            >
              {prompt}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
