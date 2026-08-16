import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '@fontsource/poppins/latin-600.css'
import '@fontsource/open-sans/latin-400.css'
import '@fontsource/open-sans/latin-700.css'
import '../../../packages/ui-brand/tokens.css'
import '../../../packages/ui-brand/base.css'
import App from './App.tsx'
import { ErrorBoundary } from './components/ErrorBoundary.tsx'

// D-347, ported from learning-web's `main.tsx`: errors a boundary cannot see - one thrown
// outside React's render/commit cycle, such as an event handler's async continuation or a
// rejected promise nobody awaited. `useChatSession` swallows some of its own failures on
// purpose (the `/chat/meta` fetch is explicitly best-effort), so these listeners exist for the
// *unintended* ones, which previously left no trace at all in a browser with the console
// closed.
//
// Logging only, with no server report - see `ErrorBoundary`'s docstring for why chat-api has
// no crash sink and why adding one is a separate decision. That also removes the re-entrancy
// hazard learning-web had to latch against: nothing here makes a network call, so a listener
// firing during an outage cannot loop.
window.addEventListener('error', (event) => {
  console.error('uncaught_error', event.message, event.filename, event.lineno)
})
window.addEventListener('unhandledrejection', (event) => {
  console.error('unhandled_rejection', event.reason)
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </StrictMode>,
)
