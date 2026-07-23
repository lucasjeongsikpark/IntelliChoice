import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '@fontsource/poppins/latin-600.css'
import '@fontsource/open-sans/latin-400.css'
import '@fontsource/open-sans/latin-700.css'
import '../../../packages/ui-brand/tokens.css'
import '../../../packages/ui-brand/base.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
