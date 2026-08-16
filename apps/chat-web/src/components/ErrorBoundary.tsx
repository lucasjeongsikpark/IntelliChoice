/**
 * The last thing between a render crash and a blank screen (D-347).
 *
 * `main.tsx` was a bare `createRoot().render(<StrictMode><App/></StrictMode>)`, so any
 * exception thrown while rendering unmounted the whole tree and left a visitor looking at
 * white space - no text, no button, no indication anything had gone wrong. learning-web
 * closed this in D-315; chat-web never did.
 *
 * **The server report now exists, and the objection this docstring used to raise is what
 * shaped it.** It read: *"chat's primary caller is anonymous (SPEC §5.19.1), so the majority
 * of chat crashes would have no token to attribute and would be dropped by the same rule. A
 * sink worth building for this app needs a different authentication answer, which is a
 * decision this component must not make on its own."* That was right, and copying
 * learning-web's token-gated reporter here would have shipped a sink that silently discarded
 * most of what it was built to catch.
 *
 * The answer lives in `chat_api.routers.client_errors`: the token is *optional*, and the
 * rate limit does the work a token was doing — per `sub` when there is one, and a single
 * shared app-wide bucket for anonymous reports, because the only id an anonymous caller could
 * be keyed on is one they can forge. Read that module for what the weaker gate gives up.
 *
 * `console.error`, deliberately, and the only place in this app that uses it. Every other
 * error path uses `console.warn` (`api/errors.ts`) because §2.6 criterion 3 counts console
 * errors and those paths are *handled*. A crash that destroyed the UI is not handled, and it
 * should fail that criterion loudly rather than hide inside a passing run.
 */

import { Component, type ErrorInfo, type ReactNode } from "react";
import { reportClientError } from "../lib/reportClientError";

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // Both, deliberately. The `console.error` stays because §2.6 criterion 3 counts console
    // errors and a crash that destroyed the UI *should* fail that criterion loudly - see this
    // file's header. The report is what makes it visible to anyone not sitting at the browser,
    // which is the gap this component's docstring recorded as a decision it should not make
    // alone. That decision is now made and lives in `chat_api.routers.client_errors`.
    console.error("react_render_crash", error, info.componentStack);
    reportClientError({
      message: error.message,
      stack: `${error.stack ?? ""}\n--- component stack ---${info.componentStack ?? ""}`,
    });
  }

  private handleReload = (): void => {
    // A plain reload, not a state reset. The session id and the transcript live in
    // `sessionStorage` (`useChatSession`), so reloading replays the conversation and
    // reconnects the stream rather than throwing the visitor's questions away. Re-rendering
    // the same crashed tree in place would just crash again on the same props.
    window.location.reload();
  };

  render(): ReactNode {
    if (this.state.error === null) return this.props.children;
    return (
      <main className="panel" role="alert">
        <h1>Something went wrong on this screen</h1>
        {/* No error text and no id to quote at support. What the visitor can act on is the
            reload, and what they need to know is that the conversation is not gone - true,
            because the transcript is in sessionStorage and the turn itself is checkpointed
            server-side. */}
        <p className="dim">
          Your conversation is saved. Reloading should put you back where you were.
        </p>
        <button onClick={this.handleReload}>Reload the page</button>
      </main>
    );
  }
}
