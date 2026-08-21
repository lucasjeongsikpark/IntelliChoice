# Live staging browser audit — 2026-08-17 (D-381)

Four `agent-browser` walks over the deployed build `gha-6841d9d9b169`: 41 flows, 101 screenshots,
**48 findings / 42 unique** (2 P1, 14 P2, 32 P3). All 36 code-mapped findings CONFIRMED against
source, none refuted. Rationale, root causes and the coverage critique are in DECISIONS D-381.

**The Playwright suite was green on this same build hours earlier (88 passed / 7 skipped) with
both P1s live in it.** That is a statement about coverage, not a failure of the suite — see the
open list at the bottom, which is the more valuable half of this audit.

> **How to cite this file, and the two things every finding here carries — added 2026-08-20
> (`AUDIT-ID-NAMESPACE` / `RISK-GROUP-AUDIT-REGISTERS`, W-17 / W-26).**
>
> **Every id from this file is cited source-qualified from now on: `AUDIT_LIVE_2026_08_17.md:AUD-L-19`,
> never a bare `AUD-L-19`.** This file **reuses the whole `AUD-L-01…AUD-L-19` range** of
> [`AUDIT_FINDINGS.md`](AUDIT_FINDINGS.md) with **unrelated meanings** — including `AUD-L-19`, the
> very id that had already been renumbered once to resolve an earlier collision. Note also that some
> bare ids *inside* this file point elsewhere: `AUD-F-27` and `AUD-F-02` below are
> `AUDIT_FINDINGS.md` findings, and prefix is not a reliable guide. Namespace map and the no-renumber
> rule: [`README.md`](README.md).
>
> **The build SHA is part of every finding (LB-05).** Everything here was measured on deployed build
> **`gha-6841d9d9b169`**. A finding measured on that build is **not automatically true of today's
> build** — HEAD has moved through Milestones 13–15 since — so re-measure before re-filing, and quote
> the SHA whenever you quote a finding.
>
> **The other two registers:** [`AUDIT_FINDINGS.md`](AUDIT_FINDINGS.md) is the S36–S39 baseline,
> frozen 2026-08-05 (D-183); [`AUDIT_2026_08_16.md`](AUDIT_2026_08_16.md) is the source-read sweep of
> the day before, over this same build, whose P2/P3 remainder this walk went and exercised live.
> **This is the only one of the three whose findings come from the running system.**

## Fixed in this pass

| id | sev | what |
|---|---|---|
| `AUD-CHAT-02` | P1 | REGRESSION: over-length question 422 falls through to the generic error instead of the length-specific message |
| `AUD-L-01` | P1 | Expired token on /dashboard never returns to sign-in — "Try again" loops forever (regression) |
| `AEL-01` | P2 | Answer-submit failure message tells the student their progress IS saved when it was not, and the accurate reco |
| `AEL-02` | P2 | Every secondary button (Skip, Flag, Submit exam, Keep working) loses its label on hover - 1.18:1 contrast in d |
| `AUD-CHAT-01` | P2 | Turn paused on an approval/consent interrupt renders a fabricated "No answer came back for that one. Try askin |
| `AUD-CHAT-03` | P2 | Approval modal has no max-height or internal scroll: on a short viewport both DECLINE and APPROVE & SEND are o |
| `AUD-CHAT-04` | P2 | Stop is client-side only: the server keeps answering and its answer later overwrites "You stopped this questio |
| `AUD-CHAT-06` | P2 | Signing in destroys the guest conversation the sign-in was supposed to preserve (stale sessionStorage owner ke |
| `AUD-L-02` | P2 | Closing the tab strands an in-flight learning session — a new session is created and prior progress is unreach |
| `AUD-L-03` | P2 | Reloading while help is on screen discards the help AND the question — the student is silently advanced |
| `AUD-L-05` | P2 | External-action approval renders both buttons below the fold — the decline button is entirely off-screen |
| `AUD-L-07` | P2 | Topic-load failure leaves a screen with zero controls |
| `EDGE-CHAT-01` | P2 | A pending approval interrupt renders the "no answer" failure line, telling the visitor to re-ask while the con |
| `EDGE-CHAT-03` | P2 | The composer loses focus on every send, so a keyboard-only visitor tabs 7 times to ask a second question |
| `AEL-03` | P3 | Dead results deep link still says 'give it another try' while offering no retry control |
| `AEL-04` | P3 | At 375x667 the primary exam action and half the answer options are below the fold |
| `AEL-05` | P3 | Unknown paths render the exam screen instead of a not-found page, leaving a bogus URL in the address bar |
| `AUD-CHAT-09` | P3 | Focus is not returned to the composer after a send completes |
| `AUD-CHAT-10` | P3 | Pasting more than 2000 characters is silently truncated - no counter, no notice |
| `AUD-CHAT-12` | P3 | A stale page-level error banner survives "New chat" and appears on the fresh welcome screen |
| `AUD-CHAT-13` | P3 | The guest header offers "sign out" even though a guest is not signed in |
| `AUD-CHAT-15` | P3 | role="log" is placed on the <main> element, so the page has no main landmark |
| `AUD-L-04` | P3 | Email-approval screen has no exit — 'Back to start' is removed while the preview is shown |
| `AUD-L-08` | P3 | Dead results deep link still says "give it another try" but offers no retry (exits now exist) |
| `AUD-L-12` | P3 | Unknown paths silently render the start screen and keep the bogus URL |
| `AUD-L-13` | P3 | Literal Markdown asterisks shown to the student in hint text |
| `AUD-L-14` | P3 | Exam answer controls sit below the fold with no sticky action bar |
| `AUD-L-15` | P3 | Chart SVGs are focusable role="application" with no accessible name |
| `AUD-L-17` | P3 | Child chooser has no sign-out or exit |
| `AUD-L-18` | P3 | Large stat rendered without thousands separator |
| `AUD-L-19` | P3 | First-time "you're starting an exciting journey" narrative replays on a mid-study resume |
| `EDGE-CHAT-05` | P3 | Light-mode follow-up chips fall below WCAG AA at 4.38:1 |
| `EDGE-CHAT-06` | P3 | A guest who never signed in is offered "sign out", and it destroys their conversation with no confirmation |
| `EDGE-CHAT-08` | P3 | An unknown deep link returns HTTP 200 and silently renders the chat app at the wrong URL |

## Not acted on, and why

- **`AUD-CHAT-05`** (P2) — Access hint never fires for a guest: role-gated questions get a bare no-source refusal with no "log in with a X account"
- **`AUD-CHAT-11`** (P3) — Connection indicator stays "Live updates connected" while the browser is offline, and its wording is screen-reader-only
- **`EDGE-CHAT-02`** (P2) — The connection indicator stays green "Live updates connected" through a full network partition - it never detects discon

`AUD-CHAT-05`'s precondition was never met: the questions it was filed against returned cited
answers, so the access-hint node never ran, and part of the complaint contradicts D-351.
`EDGE-CHAT-02`/`AUD-CHAT-11` likely measured an artifact of browser offline emulation — the
sibling walk concluded the opposite about the same mechanism. **The underlying gap is real and
open**: chat has no liveness timer and no reconnect control, where learning-web has both.

## Still open

> **⚠️ Partly overtaken, with no in-file marks until now — annotated 2026-08-20
> (`RISK-GROUP-AUDIT-REGISTERS`, W-26).** This list was maintained better than either sibling
> register and it still went stale: **five of the items that read as open below were closed on
> 2026-08-18** and the file was never patched. Verified against DECISIONS on 2026-08-20:
>
> | item | closure |
> |---|---|
> | `AUD-L-09` — raw ISO week ids and a raw attendance enum in the parent-facing blocked list | **D-407** (W15) — *"`AUD-L-09`, and the first defect the new tooling caught"* |
> | `EDGE-CHAT-07` — the send-failure message printed twice | **D-408** — closed **as accepted**: *"two channels, one event"*, so this is a written non-fix, not a pending one |
> | `AUD-L-10` — 39 skills as one comma run-on, denominator-less scores | **D-409** (W16) — grouped by the server's own classification; note the **percentage half was already fixed** when measured |
> | `AUD-L-11` — a "Review" column that promises something to open | **D-410** (W16) — the column was **renamed, not removed**; the finding's premise was wrong |
> | `AUD-CHAT-14` — out-of-scope refusal offers no escalation or contact affordance | **measured in D-412**, then **decided in D-417** *against* the recommendation — a deliberate product call, not an open defect |
>
> The three items already marked in place below (`AEL-06`, `AUD-CHAT-07`, `AUD-CHAT-08`, `AUD-L-06`,
> `AUD-L-16`) are correct as written. **What genuinely remains unmarked and unclosed: `EDGE-CHAT-04`**
> (stream disconnection conveyed only to screen readers and an 8px colour-only dot).
>
> **Worth carrying forward more than the closures:** D-411 keeps a running tally of *this list being
> wrong* — `AUD-L-16`, the approval modal, "learning-web has both a liveness timer and a reconnect
> control" (it had one), `AUD-L-06`, plus `AUD-L-10`'s percentage half and `AUD-L-11`'s premise.
> **Six**, all closed by **reading the code before implementing the note**. That habit, not the
> remaining P3s, is what this section is for.

- **`AEL-06`** ⏸ **real, and deliberately not built — analysed 2026-08-18 (D-411).** True of any SPA with no service worker: reload with no network means the browser cannot fetch `index.html`, so Chrome's offline page wins. The (S) estimate is wrong; the fix is a service worker caching the app shell, which brings cache invalidation against CloudFront's hashed assets and a new failure class (a stale shell running old JS against a new API).
  **And it would not give the student a working exam.** With the network down every API call fails regardless, and answers *cannot* be queued locally by design: AUD-F-27 and D-374 both refuse that, because "an answer that arrives after a finalize has nowhere valid to land" (AUD-F-02's 409). So the whole benefit is replacing Chrome's offline page with our own offline page. That is worth having one day and is not worth a service worker's operational surface now. Recorded with the reasoning so it is not re-filed as an (S).
- **`AUD-CHAT-07`** ✅ **resolved 2026-08-18 (D-413), and the note named the smaller half.** The composer being enabled is arguably *correct* (D-412 measured it: locking it would strand a visitor whose turn actually finished). The real defect was that the replayed "Thinking…" had **no deadline** — a turn whose snapshot never arrives pulses for the rest of the session — and it now resolves into the existing retryable state after `REQUEST_TIMEOUT_MS`, the same wait the turn would have had without the reload.
  **Two defects found by reading, neither in this note:** the **Stop button inside that bubble did nothing at all** after a reload (both in-flight refs are `null` at mount, so it aborted nothing and called nothing — the one visible exit was inert), and it aborted whatever was in flight rather than the turn whose button was clicked. Both fixed; eight guards falsified separately.
- **`AUD-CHAT-08`** ✅ **resolved 2026-08-18 (D-412)** — the `escalate: true` flag was already on the turn (D-378 put it there for `retryTurn`) and the render ignored it. Now labelled "Sent to an administrator", asserted in **both** directions since a label on both turns says nothing.
- **`AUD-CHAT-14`** ✅ **measured 2026-08-18 (D-412) and decided 2026-08-18 (D-417) — closed *against* the recommendation, which makes it a product decision rather than an open defect.** *(Marked 2026-08-20, W-26.)* Original: Out-of-scope refusal offers no escalation or contact affordance, only generic re-orientation chips
- **`AUD-L-06`** ✅ **already fixed when measured 2026-08-18 (D-411)** — D-317 fixed the position restore (the exam's position arrives on a *second* transport, and `currentDisplayOrder`'s initial `0` was being rendered as though it were an answer), and `journey-student.spec.ts:421` guards it non-vacuously: it answers **two** questions first *"so the restored position is provably not just 'the first question'"*, then asserts the question after reload equals the question before. Fourth item on this list to be closed by reading the code rather than by writing any.
- **`AUD-L-09`** ✅ **resolved 2026-08-18 (D-407, W15) — and it was the first defect the new tooling caught.** *(Marked 2026-08-20, W-26.)* Original: Raw ISO week ids and a raw attendance enum in the parent-facing blocked list
- **`AUD-L-10`** ✅ **resolved 2026-08-18 (D-409, W16)** — the 39 skills are grouped by the server's own classification, and **the percentage half was already fixed when measured** (`_RATE_FACTS` + `formatRate`), which is one of the six entries in D-411's running tally of this list being wrong. *(Marked 2026-08-20, W-26.)* Original: Generated student report dumps 39 skills as one comma run-on and shows raw, denominator-less scores · `apps/learning-web/src/components/ReportView.tsx:47` (S) — line as of build `gha-6841d9d9b169`
- **`AUD-L-11`** ✅ **resolved 2026-08-18 (D-410, W16) — the column was *renamed, not removed*, so the finding's premise was wrong.** *(Marked 2026-08-20, W-26.)* Original: "Review" column promises something to open but no history row is clickable · `apps/learning-web/src/screens/StudentDashboardScreen.tsx:733` (M) — line as of build `gha-6841d9d9b169`
- **`AUD-L-16`** ✅ **resolved 2026-08-17 (D-390)** — the link stays, with an interstitial in front of it naming where the student is going and who controls it. The embed was the other candidate and was declined; OPEN_DECISIONS #12 carries both arguments.
- **`EDGE-CHAT-04`** (P3) Stream disconnection is conveyed only to screen readers and by an 8px colour-only dot
- **`EDGE-CHAT-07`** ✅ **closed as ACCEPTED 2026-08-18 (D-408) — "two channels, one event".** A written non-fix, not a pending item; D-408's own rule (preserve the meaning rather than edit an assertion to match a change) is cited elsewhere in DECISIONS. *(Marked 2026-08-20, W-26.)* Original: The send-failure message is printed twice - once in the transcript bubble and once in the banner above the com · `apps/chat-web/src/screens/ChatScreen.tsx:413` (S) — line as of build `gha-6841d9d9b169`

## The coverage gaps, which matter more than the remaining items

> **✅ All three are closed (2026-08-17, D-383 — ROADMAP Milestone 11).** They were worth more than
> this document's P3 list, and the evidence is that **each one produced a defect within minutes of
> being looked at**: the results screen's "View progress dashboard" could not work on a completed
> session, learning-web's 400 `["attendance"]` rule was unmatchable, and chat-web's 504 rule was
> unreachable below an unconditional 5xx return. One item is deliberately still open — a genuine
> HTTP 429 has never rendered, and the escalation limiter is in-graph (a 200), so the obvious cheap
> path would not have produced one.
>
> Also corrected: gap 2's phrasing below is broader than the truth. Both approval gates were already
> approved at the **API** level; what had never happened is approving through the UI.

Three blind spots, none of them a bug and all of them a reason bugs survive:

1. **Nothing terminal has ever been completed.** No walk — manual or automated, in this project's
   whole history — has reached the post-exam results screen. `journey-student.spec.ts:28-44` says
   it stops short *by design*. The learning-gain wording, the pre→post comparison and the
   assistance counts written specifically for that screen have no live evidence at all.
2. **Every approval gate was declined, never approved.** The post-approval half of CLAUDE.md
   rule 4 is unverified: the confirmation copy, the transcript entry, the graph resuming past the
   interrupt. Staging wires `FakeEmailTransport` unconditionally, so nothing was at risk.
3. **Every failure was injected client-side.** The server-side error vocabulary has never
   rendered: 5xx, 503, 504, four rate limiters, and eight hand-written 409 messages — in a
   codebase that records a past incident where exactly that copy leaked a raw session id to a
   child.

Also never exercised: cross-account authorization (IDOR) against the deployed stack; the
cross-role RAG **denial** matrix (only the positive direction was sampled); PII redaction (no walk
typed an email address or a phone number); the exam timer running out; the student's own view of
the dashboard, which has no role gating; the calendar interrupt's three branches including the
`.ics` download; and the ErrorBoundary → client-error reporting loop.

> **Narrowed 2026-08-17 by D-385, and the two authorization items are smaller than they read.** The
> suite already covers ownership 403/404s (`test_auth.py`, `test_stream_and_history.py`) and the
> audience filter in *both* directions (74 assertions across `test_rag_search.py` and
> `test_retrieval.py`); the CDN also never caches an authenticated response (`CachingDisabled` +
> `AllViewer` on every API behaviour). So "against the deployed stack" is the whole of what is left,
> and the part of it that a test can hold is now held by
> `test_deployed_route_admission_parity.py` — the two terraform pattern lists that decide whether a
> request reaches the app at all, which nothing had checked and which has broken twice in production.
> What remains genuinely un-walked from this paragraph: one live cross-account probe, and **PII
> redaction**, which is the one worth doing next on a platform whose users are minors.
>
> **PII redaction closed the same day by D-387, and it was also narrower than it reads.** The server
> side was already held (redactor unit tests, 59 payload-floor tests, all four free-text entry points
> redacting at the boundary, learning's tutor chat asserting the persisted row), and neither app
> serves a transcript back, so a visitor's raw words never leave the tab. What was actually missing:
> `LocationConsentChoice`'s non-persistence invariant covered `latitude`/`longitude` but not the
> `zip_code`/`city`/`address` forms its own docstring claims, and no browser had checked that typed
> PII leaves the page exactly once. Both now exist; `pii-typed-by-a-visitor.spec.ts` failed its own
> falsification first, for a percent-encoding reason worth reading in D-387.
>
> **The live cross-account probe closed the same day too (D-388), scoped to deployed configuration
> rather than to the matrix.** `e2e/tests/security/deployed-authorization.spec.ts` passes 6 of 6
> against staging with no findings, and the two clauses that justify it are ones no pytest can make:
> `/dev/token` refuses to mint without the shared secret on the running service, and the CDN exposes
> none of `/metrics`, `/openapi.json`, `/docs`. Still un-walked from this paragraph: the exam timer,
> the calendar `.ics` branch, and learning-web's tutor-chat browser leg.
>
> **⚠️ The three items D-388 left "still un-walked" were all closed the same day, elsewhere, without
> updating this file — annotated 2026-08-20 (`RISK-GROUP-AUDIT-REGISTERS`, W-26).** This is the
> sharpest instance in the corpus of the class this annotation pass exists for: the never-exercised
> list was **narrowed four times in one day**, and what the paragraph above still states as un-walked
> was closed in DECISIONS while the paragraph stayed as written. Verified against DECISIONS on
> 2026-08-20:
>
> - **The exam timer running out — walked, D-391** (V10), *"the exam timer, and three defects on the
>   path nobody had walked"*. The walk itself produced three defects, which is the argument for the
>   blind-spot category over the P3 list.
> - **The calendar interrupt's `.ics` branch — walked, D-392** (V11), *"the last never-walked path,
>   and the walk that proved it cannot verify what it set out to"* — note the honesty in that title:
>   the walk ran and **could not verify the download**, which is why the coverage was then extended
>   through **D-397** (a WebKit project scoped to `calendar-branches.spec.ts`'s `@browser` tests) and
>   **D-399**.
> - **learning-web's tutor-chat browser leg — walked, D-398** (W6).
> - **The remaining item from gap 3 — a genuine HTTP 429 — is closed by watching the calls instead of
>   the browser (D-399, W7)**, which is also where D-352's rule finally got held.
>
> **Nothing in the never-exercised paragraph above is still un-walked**, and the paragraph is kept
> unedited because it is the record of what the blind-spot analysis found; this note is its forward
> pointer.

> **The ErrorBoundary loop closed 2026-08-17 (D-389), and it was broken.** Both apps posted crash
> reports to a bare relative path, so every report 404'd against the vite dev server in local
> development; it worked on staging only because the SPA and API share a distribution. Fixed to use
> `API_BASE`. `AUD-L-16` from the P3 list below is now **OPEN_DECISIONS #12** — the link-versus-embed
> choice was made deliberately with a privacy reason, so reversing it is a judgement, not a patch.
