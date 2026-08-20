> **ARCHIVED 2026-08-20 — EXECUTED PLAN.** This plan was **executed as Session 22.5** on
> 2026-07-19, the same day it was written. Its five plan-local decisions were logged as
> **BD1 → D-065, BD2 → D-066, BD3 → D-067, BD4 → D-068, BD5 → D-069**.
> **Current state: `docs/PROJECT_STATE.md`**; the as-built brand truth is
> `packages/ui-brand/tokens.css` and the brand table + BD3's standing do-not-revert rule were
> promoted to `docs/ARCHITECTURE.md`. Kept intact for the brand audit's provenance (it is derived
> from the live WordPress theme CSS) and for the phase/risk rationale.
>
> **⛔ DO NOT FOLLOW THE D-NUMBER INSTRUCTION IN THE "Decisions" HEADING BELOW.** It says to log at
> "next free D-numbers — D-064 was the last used"; that was true only on 2026-07-19. `DECISIONS.md`
> is **past D-423**, so following that line **mints duplicate decision IDs**. These decisions are
> already logged — see the BD→D map above.
>
> Two further dated statements, annotated in place below: the "planned, not started" status line, and
> the "Codebase recon (done 2026-07-19 — trust this, no need to re-derive)" section, which now
> describes **deleted** files. One superseded value: BD3's interactive pink `#d13a80` was replaced by
> **`#c22f73`** before ship (D-067). The plan's tables are **not rewritten** — the corrections are
> annotations.

# Branding plan — IntelliChoice visual identity for learning-web and chat-web (2026-07-19)

Status: **planned, not started** (user approved the plan 2026-07-19, then deferred
execution to a dedicated session — run via `/start-session S22.5`). Registered in
ROADMAP.md as Session 22.5, inserted before S23 so the new exam UI is built on brand
tokens once, not styled twice.

> **Annotation 2026-08-20:** the status line above is **stale as written** — S22.5 ran and
> completed on **2026-07-19**, the same day the plan was approved and "deferred". Evidence:
> `DECISIONS.md` D-065–D-069 all dated 2026-07-19 and labelled "S22.5"; the as-built
> `packages/ui-brand/` exists. Read "planned, not started" as a 2026-07-19T-approval-time
> statement only.

Source of truth for branding: the live `www.intellichoice.org` site (Impreza WordPress
theme options CSS, extracted 2026-07-19 — see the audit table below; no need to
re-scrape unless values look wrong).

## Brand audit (extracted from the live site's `us-theme-options-css` `:root` block)

| Element | Value |
|---|---|
| Heading font | Poppins 600 (site h1 3.5rem → h6 1.2rem; mobile h1 2.5rem; letter-spacing −0.02em) |
| Body font | Open Sans 400/700; text `#333333`, headings `#1a1a1a`, muted `#999999` |
| Primary | Green `#5eb761` — links, buttons, header/footer link hover |
| Accent pair | Pink `#e95095` → purple `#7049ba` as `linear-gradient(135deg, #e95095, #7049ba)` on highlight sections |
| Primary faded | `rgba(94,183,97,0.15)` (the site's own tint token) |
| Surfaces | bg `#ffffff`, alt bg `#f5f5f5`, border `#e8e8e8`, footer `#222222` (footer text `#999`, link `#ccc`, hover green) |
| Shadow | `0 5px 15px rgba(0,0,0,.15)`; content max width 1200px |
| Buttons | uppercase, 600, 16px, radius `0.3em`, padding `0.9em 1.8em`, solid green → hover secondary; 2px outline variant |
| Logo | horizontal PNG, top-left of white header; header text `#333` → hover green |

Logo asset URLs (download at session start; check real dimensions with `sips`
before choosing favicon treatment — the "512x512" in the filename is upload-name
noise, the rendered crop is 300×67 so the original is almost certainly wide):

- original: `https://www.intellichoice.org/wp-content/uploads/2021/12/intellihoice-logo-512x512-1.png`
- 300×67 render: `https://www.intellichoice.org/wp-content/uploads/2021/12/intellihoice-logo-512x512-1-300x67.png`

The site's own dark-scheme CSS block is untouched Impreza theme defaults (a different
green entirely) — **not** brand truth; we design our own dark variants.

## Scope by layer

- **Frontend:** all of the work.
- **Backend / DB / LangGraph / Memory / RAG:** no changes. Purely client-side.
- **Evaluation:** no changes to existing evals. New frontend-local verification:
  contrast-assertion script over the token file, Playwright screenshot walk (S16/S21
  pattern), optional axe pass.

## Decisions (log into DECISIONS.md at session start, next free D-numbers — D-064 was
## the last used as of 2026-07-19)

> **⛔ STOP — DO NOT FOLLOW THIS INSTRUCTION. Annotation 2026-08-20.** "D-064 was the last used"
> was true only on 2026-07-19. **`DECISIONS.md` is past D-423**, so allocating "the next free
> D-numbers" from D-065 **mints duplicate decision IDs** on top of decisions that already exist.
> **These five decisions were already logged**, on 2026-07-19, as:
> **BD1 = D-065**, **BD2 = D-066**, **BD3 = D-067**, **BD4 = D-068**, **BD5 = D-069**
> (`docs/DECISIONS.md:1428, 1457, 1470, 1498, 1512`, each headed "S22.5"). Nothing here is
> pending. If a future session needs a new decision id, read the end of `DECISIONS.md` — never
> this line.

- **BD1 — tokens live in one shared source** `packages/ui-brand/` (tokens.css, base.css,
  logo assets, README, contrast checker). Both apps import via relative path from
  `main.tsx`; each `vite.config.ts` gets `server.fs.allow: ["../.."]` (repo root) — the
  two apps have separate lockfiles, so Vite can't infer the monorepo root and refuses to
  serve files outside the app dir by default. Fallback if this breaks in Docker: checked
  duplication with a `diff` guard in CI. Rationale: the two apps' `index.css` were
  byte-identical before this work — hand-synchronized duplication already existed.
  **Share CSS and assets only, not TSX components**: both apps' `tsconfig.app.json`
  include only `["src"]`, so a cross-app TSX import breaks `tsc -b` (TS6059 rootDir);
  chrome markup stays per-app (~30 lines each, and it genuinely differs).
- **BD2 — fonts self-hosted via `@fontsource`** (`@fontsource/poppins` 600.css,
  `@fontsource/open-sans` 400.css + 700.css), not the Google Fonts CDN the site uses:
  primary users are minors and a CDN font request ships every student's IP to Google;
  also keeps offline/local dev working. OFL/Apache licenses permit self-hosting.
- **BD3 — deliberate contrast deviation (do not "fix" back).** Brand green `#5eb761` on
  white is **2.49:1** and pink `#e95095` is **3.47:1** — both fail WCAG AA 4.5:1 (the
  live site itself fails). Two-tier tokens: raw brand colors for identity/decorative/
  large uses; darkened interactive tones — green `#387e40` (4.97:1), pink `#d13a80`
  (4.54:1) — for links, button backgrounds, text-sized color. Purple `#7049ba`
  (6.27:1) passes as-is.
  > **Annotation 2026-08-20 — one value superseded, the rule stands.** BD3's *rule* (two tiers, do
  > not "fix" the interactive tier back to raw brand hex) shipped and is standing — see D-067 and
  > `docs/ARCHITECTURE.md`. But the interactive **pink `#d13a80` above was superseded by
  > `#c22f73`** before ship: the plan's 4.54:1 was checked only against `--panel-bg` (white), and
  > against the page background token `--bg: #f5f5f5` the same hex drops to **4.16:1 — a real
  > WCAG AA fail**. Shipped values (`packages/ui-brand/tokens.css:37`): pink `#c22f73` (4.88:1 on
  > `--bg`, 5.32:1 on `--panel-bg`); green `#387e40` unchanged; `--error` darkened `#dc2626` →
  > `#d32020` for the identical reason (`docs/DECISIONS.md:1470–1495`). The table above is left
  > unedited as the plan's own draft; `tokens.css` is the value of record.
- **BD4 — dark mode kept**, brand-adapted variants designed here (lightened green for
  dark surfaces + an `--accent-contrast` token, because white-on-light-green fails —
  dark-mode solid buttons need dark text on the lightened green).
- **BD5 — plain CSS custom properties stay**; no Tailwind/CSS-in-JS. The existing
  ~680-line token-driven CSS surface is small and working.

## Codebase recon (done 2026-07-19 — trust this, no need to re-derive)

> **Annotation 2026-08-20 — do NOT trust this section; the plan changed the code it describes.**
> "no need to re-derive" was written before Phase 1 ran. The two files this recon is built on,
> `apps/learning-web/src/index.css` and `apps/chat-web/src/index.css`, **no longer exist** (verified
> absent 2026-08-20); their content moved to `packages/ui-brand/tokens.css` + `base.css`, exactly as
> Phase 1 below planned ("shrink each `index.css` to app-local remainder (or delete)"). The generic
> purple `#7c3aed` token value is also gone. The screen inventory is likewise a 2026-07-19 count —
> learning-web has since gained `StageTransitionScreen`, `StudentDashboardScreen` and
> `BookmarkedResultsScreen`, among other post-S22.5 additions. Re-derive from the code before
> relying on any file path, token name or screen list below.

- Two independent Vite+React apps, deps = react/react-dom only, plain CSS, no
  framework. `apps/learning-web/src/index.css` and `apps/chat-web/src/index.css` are
  **byte-identical**: a semantic token block (`--text`, `--text-h`, `--bg`,
  `--panel-bg`, `--border`, `--code-bg`, `--accent`, `--accent-hover`, `--accent-bg`,
  `--error`, `--success`, `--shadow`, `--sans`, `--mono`; currently generic purple
  `#7c3aed`) + element base styles (box-sizing, body, h1/h2, code) + a
  `prefers-color-scheme: dark` override block. All component CSS
  (`App.css`, 254 lines learning / 354 lines chat) consumes these via `var()`, so
  **retargeting the tokens rebrands ~80% of the UI**.
- Screens: learning-web 9 (`DevLogin`, `Start`, `ChildSelection`, `TopicSelect`,
  `Attendance`, `Exam`, `Intervention`(=`AssistancePanel`), `Results`,
  `ParentDashboard`); chat-web 7 (`DevLogin`, `Chat`, `WelcomeCard`,
  `AccessHintBanner`, `EmailApproval`/`CalendarAction`/`LocationConsent` modals).
- `learning-web/src/App.tsx` is an early-return if-chain over `snapshot.phase` — every
  branch returns a full-page element centered by `#root` flex. To add persistent
  chrome, wrap the existing chain in an inner `function view(): ReactNode` (keeps all
  closures) and return `<div className="app-shell"><header/><main>{view()}</main>
  <footer/></div>` once; move `#root`'s centering styles onto `.app-main`.
- `chat-web` already has a `.chat-header` inside `ChatScreen` (h1 + who + logout) and
  sizes `.chat-page` as `calc(100svh - 48px)` against `#root`'s 24px padding — if a
  shell header/footer is added there, that calc must become flex (`flex: 1;
  min-height: 0`) or the page will overflow. Lower-risk alternative chosen: put the
  logo inside the existing `.chat-header` and skip a separate shell bar for chat.
- Both `App.css` files define an element-level `button` rule (solid accent, white
  text) plus variants `button.secondary`, `button.link` (slightly different between
  apps), and content-bearing button classes that must **not** be uppercased:
  `.option` (exam answer choices), `.card` (child selection), `button.link`,
  `button.chip` (chat suggestion chips). The brand's uppercase/600 treatment applies
  only to action buttons — add `text-transform: none` to those four classes.
- `index.html` titles already correct ("IntelliChoice Adaptive Learning" /
  "IntelliChoice Q&A"); each app has a placeholder `public/favicon.svg` to replace.

## Token mapping (new `packages/ui-brand/tokens.css`; keep the existing semantic names)

Light: `--text: #333333`, `--text-h: #1a1a1a`, `--bg: #f5f5f5` (page),
`--panel-bg: #ffffff`, `--border: #e8e8e8`, `--code-bg: #f5f5f5`,
`--accent: #387e40`, `--accent-hover: #2f6b36`, `--accent-bg: rgba(94,183,97,0.15)`,
`--accent-contrast: #ffffff`, `--error: #dc2626`, `--success: #387e40`,
`--shadow: 0 5px 15px rgba(0,0,0,0.08)` (site's geometry, softened for app density).
Raw brand tier: `--brand-green: #5eb761`, `--brand-pink: #e95095`,
`--brand-purple: #7049ba`, `--pink-interactive: #d13a80`,
`--brand-gradient: linear-gradient(135deg, #e95095, #7049ba)`.
Fonts: `--sans: "Open Sans", system-ui, sans-serif`,
`--heading: "Poppins", var(--sans)` (weight 600, letter-spacing −0.02em on h1–h3);
type scale capped ~1.75–2rem for app density (not the marketing site's 3.5rem).
Dark (own design per BD4, validate with the contrast script): near-neutral dark
surfaces (bg ≈ `#131513`, panel ≈ `#1c1f1d`, border ≈ `#2e332f`), lightened green
accent ≈ `#7cc880` with `--accent-contrast` ≈ `#0c1f10` (dark text on light-green
buttons), lightened pink/purple ≈ `#ef6ba6`/`#9d7fd6`.
Also add: radius tokens (panel 12px, control 8px, button ≈6px per the site's 0.3em),
spacing scale, `--footer-bg: #222222`.
Buttons: uppercase, 600, 15–16px, letter-spacing 0.02em; solid / neutral-secondary /
outline variants; the gradient reserved as a sparse highlight device (results/progress
moments), mirroring the site's alt-section role.

## Phases

1. **Foundation:** create `packages/ui-brand/` (tokens.css per the mapping above,
   base.css with element styles moved out of the twin index.css files, downloaded logo
   assets, favicon derived from the logo, README, `check_contrast.py`). Wire both
   apps: `npm i @fontsource/poppins @fontsource/open-sans` in each; `main.tsx` imports
   (fontsource weights, then `../../../packages/ui-brand/tokens.css` + `base.css`);
   `server.fs.allow` in both vite configs; shrink each `index.css` to app-local
   remainder (or delete).
2. **Chrome:** learning-web app-shell header (logo + product name) + slim footer
   ("© IntelliChoice Inc." + link to intellichoice.org) via the `view()` wrap
   described in recon; chat-web logo into the existing `.chat-header`; replace both
   favicons; add logo to both DevLogin panels.
3. **Component/screen pass:** buttons (solid/neutral/outline, uppercase 600 with the
   four content-class exclusions), links, inputs, chips, citation chips, modals,
   banners, exam/intervention/results screens, parent dashboard; dark tuning pass.
   Student-facing wording untouched (SPEC rule 10).
4. **Verification:** `npm run build` + `npm run lint` in both apps; Playwright
   screenshot walk of every screen, light + dark (S16/S21 pattern, dev servers :8001/
   :5173 for learning, chat equivalents); run `check_contrast.py` (assert every
   text/background token pair ≥ 4.5:1, button text vs button bg included, both
   schemes); update PROGRESS.md / DECISIONS.md / ROADMAP.md per session workflow.

## Risks

- Contrast deviation is a deliberate brand deviation (BD3) — record it so it isn't
  reverted later.
- `server.fs.allow` across separate lockfiles is the mechanically fiddly bit
  (dev-server only — production `vite build` bundles fine regardless); fallback ready.
- Raster logo may look soft at large sizes; display ≤150px width from the largest
  source; ask the org for an SVG original.
- Chat's `calc(100svh - 48px)` height breaks if a shell bar is added without the flex
  restructure (see recon) — the chosen design avoids this.
- Must precede S23 so the exam UI is built on tokens once; S23's accessibility scope
  can reuse the contrast/axe tooling introduced here.
