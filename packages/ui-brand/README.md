# packages/ui-brand

Shared visual identity for `learning-web` and `chat-web` (S22.5, D-065–D-069).
CSS and static assets only — no TSX components (see D-065 for why).

## Contents

- `tokens.css` — brand color/font/spacing custom properties, `:root` (light) +
  `@media (prefers-color-scheme: dark)` override. Keeps the same semantic
  token names (`--text`, `--accent`, ...) the apps already used before
  branding, so App.css files needed no renames.
- `base.css` — bare-element styles (`h1`–`h3`, `code`, `a`, box-sizing) shared
  by both apps.
- `assets/logo.png` — brand wordmark (512×115), downloaded from the live
  `www.intellichoice.org` site 2026-07-19. Display at ≤150px width; a raster
  logo looks soft scaled larger. Ask the org for an SVG original before this
  becomes a visible problem.
- `assets/favicon.svg` — the logo's three-dot mark, redrawn as flat circles
  (exact colors sampled from `logo.png`'s pixels, not from the site's theme
  CSS — this mark uses its own palette).
- `check_contrast.py` — WCAG AA (4.5:1) checker for every real text/background
  token pair in `tokens.css`. Run before touching any color in this file:
  `python3 packages/ui-brand/check_contrast.py`.

## Two-tier color system (D-067)

Raw brand colors (`--brand-green`, `--brand-pink`, `--brand-purple`) fail WCAG
AA as text on white/near-white — the live site itself fails this. Use them
only for decorative/identity/large-surface purposes (logo, gradient highlight
sections). For any text-sized use (links, button backgrounds, focus states),
use the darkened "interactive" tier instead: `--accent`, `--accent-hover`,
`--pink-interactive`. `check_contrast.py` only checks the interactive tier —
it's the one actually rendered as text.

## Consuming this package

Both apps import via a relative path from `main.tsx` (order matters — fonts
first, then tokens, then base; each app's own `App.css` is imported
separately from `App.tsx` and layers on top). Only the `latin` subset is
pulled in — `@fontsource`'s default `600.css`/`400.css`/`700.css` entrypoints
bundle every Unicode range (Cyrillic, Greek, Devanagari, math symbols, ...),
which this project never needs:

```ts
import "@fontsource/poppins/latin-600.css";
import "@fontsource/open-sans/latin-400.css";
import "@fontsource/open-sans/latin-700.css";
import "../../../packages/ui-brand/tokens.css";
import "../../../packages/ui-brand/base.css";
```

Each app's `vite.config.ts` needs `server.fs.allow: ["../.."]` (repo root) for
the dev server to serve files outside the app directory — the two apps have
separate lockfiles, so Vite can't infer a shared monorepo root on its own.
Production `vite build` bundles fine regardless of `fs.allow` (dev-server-only
restriction).

## Editing a token

1. Change the value in `tokens.css`.
2. Run `check_contrast.py` — it must exit 0 before you commit.
3. If you're introducing a *new* brand color, give it the same raw/interactive
   split described above before using it for text (D-067).
