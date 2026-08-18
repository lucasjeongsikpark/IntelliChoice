import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // D-405: vitest reads its config from here rather than a separate `vitest.config.ts`, so the
  // plugins and resolution above cannot drift from what the tests run against.
  //
  // **Why this exists at all** (OPEN_DECISIONS #14): neither frontend had any test tooling, and
  // four properties this project wanted turned out to be inexpressible without it - `errors.ts`'s
  // status-to-message rules, `downloadIcs`'s DOM contract (covered the expensive way instead via
  // a Playwright probe), "the disconnect banner renders for `error` and nothing else" (a browser
  // test was written for it, measured flaky, and deleted), and the stream liveness timer, whose
  // 40s timeout cannot be shortened from a browser test. The browser suite stays the place where
  // real contracts against real APIs are checked; this is for pure logic and timers.
  test: {
    // `jsdom` for `window`/`document`. `EventSource` is *not* implemented by jsdom, which is
    // convenient rather than a limitation: the stream tests install their own fake, so what they
    // drive is fully controlled instead of half-real.
    environment: "jsdom",
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
  },
  server: {
    // packages/ui-brand lives outside this app dir; the two apps have
    // separate lockfiles so Vite can't infer a shared monorepo root (D-065).
    fs: { allow: ['../..'] },
  },
})
