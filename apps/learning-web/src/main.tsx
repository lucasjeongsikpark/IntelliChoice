import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import '@fontsource/poppins/latin-600.css'
import '@fontsource/open-sans/latin-400.css'
import '@fontsource/open-sans/latin-700.css'
import '../../../packages/ui-brand/tokens.css'
import '../../../packages/ui-brand/base.css'
import App from './App.tsx'
import { ErrorBoundary } from './components/ErrorBoundary.tsx'
import { reportClientError } from './lib/reportClientError'

// An error a boundary cannot see: one thrown outside React's render/commit cycle - an event
// handler's async continuation, or a rejected promise nobody awaited. `useLearningSession`
// swallows its own failures on purpose (fire-and-forget telemetry, best-effort storage
// writes), so these listeners exist for the *unintended* ones, which previously left no trace
// at all in a browser with the console closed. Logging only: a sink is a separate decision -
// see `ErrorBoundary`'s docstring.
window.addEventListener('error', (event) => {
  console.error('uncaught_error', event.message, event.filename, event.lineno)
  reportClientError({
    message: `uncaught_error: ${event.message}`,
    stack: `${event.filename}:${event.lineno}`,
  })
})
window.addEventListener('unhandledrejection', (event) => {
  console.error('unhandled_rejection', event.reason)
  // U5/D-328: `reportClientError` latches itself off after its own fetch fails, which is what
  // stops this listener from re-entering when the API is the thing that is down.
  reportClientError({ message: `unhandled_rejection: ${String(event.reason)}` })
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ErrorBoundary>
      {/* U4/D-327: the router wraps the boundary's child rather than the boundary itself, so a
          render crash is still caught by `ErrorBoundary` and is not turned into a routing
          error. §5.1.2's first-visit disclosures are route-aware, which is why this exists
          before there is a second page worth navigating to. */}
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </ErrorBoundary>
  </StrictMode>,
)
