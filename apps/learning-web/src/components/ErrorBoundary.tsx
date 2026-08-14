/**
 * The last thing between a render crash and a blank screen.
 *
 * There was nothing here before: `main.tsx` was a bare
 * `createRoot().render(<StrictMode><App/></StrictMode>)`, so any exception thrown while
 * rendering unmounted the whole tree and left a K-12 student looking at white space with no
 * text, no button, and no indication that anything had gone wrong. The only place in this
 * repo that has ever observed such a crash is the e2e harness (`capture.ts:149` listens for
 * `pageerror`, with its own comment noting that a React render crash surfaces there and not
 * in `console`) - which is test-time only. In production nobody, including the student,
 * learned anything.
 *
 * **Scope, stated because it is easy to over-read.** This is a recovery UI and a console
 * record. It is *not* error reporting: there is no sink, so a crash still does not reach the
 * maintainer. Sending one needs a decision this component should not make on its own - an
 * authenticated endpoint, a rate limit, and a PII rule for message/stack text (SPEC §5.30,
 * and a React error message can quote rendered content). Recorded as carry-over rather than
 * guessed at here.
 *
 * `console.error`, deliberately, and this is the one place in the app that uses it. Every
 * other error path uses `console.warn` (`api/errors.ts:139`) because §2.6 criterion 3 counts
 * console errors and those paths are *handled*. A crash that destroyed the UI is not handled,
 * and it should fail that criterion loudly rather than hide inside a passing run.
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
    // which is the gap U5/D-328 closes and which this component's docstring recorded as a
    // decision it should not make alone.
    console.error("react_render_crash", error, info.componentStack);
    reportClientError({
      message: error.message,
      stack: `${error.stack ?? ""}\n--- component stack ---${info.componentStack ?? ""}`,
    });
  }

  private handleReload = (): void => {
    // A plain reload, not a state reset. The session id lives in `sessionStorage`
    // (`useLearningSession`), so reloading resumes the same session at the same phase rather
    // than starting over - which is exactly what a student who was mid-exam needs, and is
    // the behaviour SPEC Phase 11's refresh requirement already guarantees. Re-rendering the
    // same crashed tree in place would just crash again on the same props.
    window.location.reload();
  };

  render(): ReactNode {
    if (this.state.error === null) return this.props.children;
    return (
      <main className="panel" role="alert">
        <h1>Something went wrong on this screen</h1>
        {/* No apology-plus-blame, no error text, no id to quote at support. What a student
            can act on is the reload, and what they need to know is that their work is not
            gone - both true, because answers are committed server-side per submission and
            the session resumes from the checkpoint. §5.10.3's register: not their fault, not
            catastrophic, and there is a next step. */}
        <p className="subtitle">
          Your work is saved. Reloading should put you back where you were.
        </p>
        <button onClick={this.handleReload}>Reload the page</button>
      </main>
    );
  }
}
