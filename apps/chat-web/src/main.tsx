import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '@fontsource/poppins/latin-600.css'
import '@fontsource/open-sans/latin-400.css'
import '@fontsource/open-sans/latin-700.css'
import '../../../packages/ui-brand/tokens.css'
import '../../../packages/ui-brand/base.css'
import App from './App.tsx'
import { ErrorBoundary } from './components/ErrorBoundary.tsx'
import { reportClientError } from './lib/reportClientError.ts'

// D-347, ported from learning-web's `main.tsx`: errors a boundary cannot see - one thrown
// outside React's render/commit cycle, such as an event handler's async continuation or a
// rejected promise nobody awaited. `useChatSession` swallows some of its own failures on
// purpose (the `/chat/meta` fetch is explicitly best-effort), so these listeners exist for the
// *unintended* ones, which previously left no trace at all in a browser with the console
// closed.
//
// These now report as well as log. The comment here used to say the opposite - "logging only,
// with no server report" - and noted that it removed the re-entrancy hazard learning-web had to
// latch against, because nothing in this path made a network call. Adding the report adds that
// hazard back: a `fetch` that rejects during an outage is itself an unhandled rejection, which
// re-enters the listener below. `reportClientError` carries the latch for exactly that reason.
window.addEventListener('error', (event) => {
  console.error('uncaught_error', event.message, event.filename, event.lineno)
  reportClientError({
    message: event.message,
    stack: `${event.filename ?? ''}:${event.lineno ?? ''}`,
  })
})
window.addEventListener('unhandledrejection', (event) => {
  console.error('unhandled_rejection', event.reason)
  reportClientError({
    message: String(event.reason?.message ?? event.reason ?? 'unhandled rejection'),
    stack: event.reason?.stack,
  })
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </StrictMode>,
)
