/**
 * The last thing between a render crash and a blank screen (D-347).
 *
 * `main.tsx` was a bare `createRoot().render(<StrictMode><App/></StrictMode>)`, so any
 * exception thrown while rendering unmounted the whole tree and left a visitor looking at
 * white space - no text, no button, no indication anything had gone wrong. learning-web
 * closed this in D-315; chat-web never did.
 *
 * **No server report, and that is a decision rather than an omission.** learning-web's
 * boundary posts to `/learning/client-errors`, which requires a bearer token by design - an
 * open crash sink is a log-injection endpoint. chat-api has no equivalent, and adding one
 * would help less here than it does there: chat's primary caller is *anonymous* (SPEC
 * §5.19.1), so the majority of chat crashes would have no token to attribute and would be
 * dropped by the same rule. A sink worth building for this app needs a different
 * authentication answer, which is a decision this component must not make on its own. Filed
 * as carry-over; console-only until then.
 *
 * `console.error`, deliberately, and the only place in this app that uses it. Every other
 * error path uses `console.warn` (`api/errors.ts`) because §2.6 criterion 3 counts console
 * errors and those paths are *handled*. A crash that destroyed the UI is not handled, and it
 * should fail that criterion loudly rather than hide inside a passing run.
 */

import { Component, type ErrorInfo, type ReactNode } from "react";

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
    console.error("react_render_crash", error, info.componentStack);
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
