# Live staging browser audit — 2026-08-17 (D-381)

Four `agent-browser` walks over the deployed build `gha-6841d9d9b169`: 41 flows, 101 screenshots,
**48 findings / 42 unique** (2 P1, 14 P2, 32 P3). All 36 code-mapped findings CONFIRMED against
source, none refuted. Rationale, root causes and the coverage critique are in DECISIONS D-381.

**The Playwright suite was green on this same build hours earlier (88 passed / 7 skipped) with
both P1s live in it.** That is a statement about coverage, not a failure of the suite — see the
open list at the bottom, which is the more valuable half of this audit.

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

- **`AEL-06`** (P3) Reloading mid-exam with no network drops the student out of the app entirely (Chrome offline page) · `apps/learning-web/src/main.tsx:33` (S)
- **`AUD-CHAT-07`** (P3) After a mid-turn reload the composer and Send are re-enabled while the in-flight turn still shows "Thinking…" · `apps/chat-web/src/hooks/useChatSession.ts:68` (M)
- **`AUD-CHAT-08`** (P3) Escalating re-appends your question verbatim and unlabelled, so the transcript looks like you asked it twice
- **`AUD-CHAT-14`** (P3) Out-of-scope refusal offers no escalation or contact affordance, only generic re-orientation chips
- **`AUD-L-06`** (P3) Mid-exam reload restores the first unanswered question, not the student's actual position · `apps/learning-web/src/screens/ExamScreen.tsx:323` (M)
- **`AUD-L-09`** (P3) Raw ISO week ids and a raw attendance enum in the parent-facing blocked list
- **`AUD-L-10`** (P3) Generated student report dumps 39 skills as one comma run-on and shows raw, denominator-less scores · `apps/learning-web/src/components/ReportView.tsx:47` (S)
- **`AUD-L-11`** (P3) "Review" column promises something to open but no history row is clickable · `apps/learning-web/src/screens/StudentDashboardScreen.tsx:733` (M)
- **`AUD-L-16`** (P3) Video help sends a minor to the full youtube.com watch page in a new tab · `apps/learning-web/src/screens/InterventionScreen.tsx:379` (M)
- **`EDGE-CHAT-04`** (P3) Stream disconnection is conveyed only to screen readers and by an 8px colour-only dot
- **`EDGE-CHAT-07`** (P3) The send-failure message is printed twice - once in the transcript bubble and once in the banner above the com · `apps/chat-web/src/screens/ChatScreen.tsx:413` (S)

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
