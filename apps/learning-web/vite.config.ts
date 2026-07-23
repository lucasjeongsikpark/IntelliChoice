import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // packages/ui-brand lives outside this app dir; the two apps have
    // separate lockfiles so Vite can't infer a shared monorepo root (D-065).
    fs: { allow: ['../..'] },
  },
})
