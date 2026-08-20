# The first-visit notice — SPEC §5.1.2's eleven disclosures, enumerated (T-02)

**What this is.** The eleven disclosures SPEC §5.1.2 requires on a student's first visit to
`learning.intellichoice.org`, each written out as copy, and each paired with the system fact it
has to stay true to. **S45 transcribes this; it does not draft it** — that split is the whole
point of the file. D-127 §3 filed T-02 because the notice's *content* depended on an unstarted
legal track while its *implementation* was assumed by a session that never listed it, which is
how a requirement arrives at launch owned by nobody.

**What this is not.** Not the Privacy Notice, and not a substitute for counsel review, which
stays a launch gate (§6.1). Not the capture UI, the age-band derivation, or the consent record —
those are S45's build. And **not parental consent**: §5.1.2 is explicit that a student-facing
notice may not stand in for it. For an under-13 student the app verifies
`parental_consent_verified=true` from the existing `go.intellichoice.org` system *first*, and only
then shows this notice.

**Two registers.** The token carries `student_age_band`
([auth.py](../packages/shared/src/intellichoice_shared/auth.py)), so the copy below comes in a
younger-reader form and a standard form. The younger form is the one to use when in doubt: no
disclosure below is materially harder to state simply, and the product's primary users are minors.

---

## 1. How to read each entry

| field | means |
|---|---|
| **SPEC line** | the requirement, verbatim from §5.1.2 — the thing that must be disclosed |
| **Copy** | what the student reads. Two registers |
| **True because** | the code or decision that makes the sentence accurate today |
| **Goes false if** | the change that would silently turn the notice into a false statement |

A disclosure whose "True because" row says **NOT BUILT** must not ship as written. §5 collects
those three.

---

## 2. The eleven disclosures

### 2.1 AI analyzes student answers and learning history

- **Copy (younger):** "A computer program looks at your answers to figure out what to give you next."
- **Copy (standard):** "An AI system reviews your answers and your past sessions to choose what you practise next."
- **True because:** the study plan is selected from the student's own mastery estimates and
  attempt history; `semantic_memory` holds consolidated facts about the learner
  ([packages/memory](../packages/memory)). Grading itself is **not** the AI — see 2.3.
- **Goes false if:** selection stops being personalized (then it over-claims), or the AI starts
  reading something beyond answers and learning history.

### 2.2 AI-generated hints and explanations may contain errors

- **Copy (younger):** "Sometimes the hints are wrong. If a hint looks strange, tell your tutor."
- **Copy (standard):** "AI-written hints and explanations can be wrong. If something looks
  incorrect, you can report the question, and you should ask your tutor."
- **True because:** hints and explanations are model output. The pipeline constrains them —
  JSON-schema output, Pydantic validation, a bounded repair retry, then a deterministic fallback
  (SPEC §5.25.3/§5.27) — which reduces malformed output, not wrongness.
- **Goes false if:** nothing. This one is permanently true and is the most important sentence in
  the notice.

### 2.3 AI does not replace a teacher or tutor

- **Copy (younger):** "This is practice, not a teacher. Your tutor is still your teacher."
- **Copy (standard):** "This tool supports your learning; it does not replace your teacher or
  tutor."
- **True because:** a design rule rather than a feature — grading, attendance gating,
  authorization and score calculation are deterministic and never done by an LLM (SPEC §5.0,
  §5.26). Worth saying plainly in the notice: **the AI does not decide whether an answer is
  right.**
- **Goes false if:** an LLM is ever put on the grading path.

### 2.4 Pre-exam and post-exam results adjust the estimated level

- **Copy (younger):** "Your first and last quizzes help us pick the right level for you."
- **Copy (standard):** "Your pre-exam and post-exam results are used to update the level we
  estimate for you, which changes the difficulty of what you get next."
- **True because:** the pre/post pair drives the mastery estimate and the learning-gain
  calculation; `learning_gain` rows are written at post-exam completion
  ([flow.py](../apps/learning-api/src/learning_api/services/flow.py)).
- **Goes false if:** the estimated level stops feeding item selection.

### 2.5 Scores and skills to strengthen may be shared in limited form with tutors and branch managers

- **Copy (younger):** "Your tutor and your branch manager can see how you are doing."
- **Copy (standard):** "Your tutor and branch manager may see a limited summary — your scores and
  the skills to work on — not your individual answers or chat messages."
- **True because:** ⚠️ **NOT BUILT in this codebase.** `tutor` and `branch_manager` are defined
  roles ([auth.py](../packages/shared/src/intellichoice_shared/auth.py)) and gate document
  retrieval in the Q&A app, but learning-api exposes **no tutor- or manager-facing view of a
  student's record**; the read half is deferred to S43/integration (D-086). See §5.
- **Goes false if:** it ships wider than "scores and skills" — the word *limited* is doing real
  work and the eventual view must be built to match it.

### 2.6 Parents can view the child's complete learning record and generated reports

- **Copy (younger):** "Your parent can see everything you do here, including your reports."
- **Copy (standard):** "A linked parent can view your complete learning record and the reports
  generated from it."
- **True because:** parent access is implemented and server-verified — the parent-child link is
  checked in the backend, never inferred from a request (SPEC §5.21.3, §5.30.2), and
  `student_reports` serves parent-visible history.
- **Goes false if:** nothing planned. Note the honesty requirement: **"complete" means complete**,
  including tutor-chat messages within their retention window. Do not soften it.

### 2.7 Student questions and learning events may be used to create learning memory

- **Copy (younger):** "We remember what you found tricky, so next time fits you better."
- **Copy (standard):** "Your questions and what happens in a session are used to build a learning
  memory that personalizes future sessions. It is kept for 90 days after it was last confirmed."
- **True because:** `semantic_memory` holds consolidated facts, refreshed by the weekly
  consolidation job and purged 90 days after `last_confirmed_at`
  ([retention_purge_cli.py](../apps/learning-api/src/learning_api/services/retention_purge_cli.py),
  D-114).
- **Goes false if:** the 90-day window moves, or memory starts being derived from a source the
  sentence does not name.

### 2.8 Uploaded solution images are deleted immediately after analysis

- **Copy (younger):** "If you send a photo of your work, we delete it as soon as we read it."
- **Copy (standard):** "A photo of your work is deleted immediately after it is analyzed, whether
  the analysis succeeds or fails. It is never kept, backed up, or logged."
- **True because:** ⚠️ **NOT BUILT.** S29 (multimodal solution images) is deferred and not started
  (D-078) — there is no upload endpoint, so there are no images. See §5.
- **Goes false if:** it ships. When S29 is built, the deletion-on-failure path and the
  no-bytes-in-logs rule are what make this sentence true (SPEC §5.17), and its own "done when"
  already requires a test proving the file is gone.

### 2.9 External YouTube learning resources may be recommended

- **Copy (younger):** "Sometimes we show you a video from YouTube to help."
- **Copy (standard):** "We may recommend a YouTube video to help with a skill. Watching it takes
  you to YouTube, which has its own rules and privacy policy."
- **True because:** built and stocked — 102 of 112 skills have a servable video (D-337/D-339).
- **Goes false if:** the catalog is disabled, or recommendations start being embedded in-page in
  a way that makes "takes you to YouTube" untrue.

### 2.10 Data sent to external AI, AWS, and observability systems is minimized and de-identified

- **Copy (younger):** "We do not send your name or your email to the AI."
- **Copy (standard):** "When we use AI or send data to our cloud and monitoring systems, we keep
  it to the minimum needed and leave out information that identifies you, such as your name and
  email address."
- **True because:** the product's hardest architectural rule. Postgres stores only
  `*_external_id` references and no PII; the org's MySQL database stays the source of truth for
  names, emails and relationships (SPEC §5.4, §5.30); a schema-purity test enforces the shape,
  and a PII denylist filter covers logs.
- **Goes false if:** any PII field lands in Postgres, a log, a trace, or an LLM payload. This is
  the disclosure with the most machinery already defending it — keep the claim exactly this
  narrow, since "de-identified where possible" is the SPEC's own hedge and the copy should not
  upgrade it to a guarantee.

### 2.11 Students can challenge learning results or report problematic questions

- **Copy (younger):** "If a question looks wrong, you can tell us."
- **Copy (standard):** "You can report a question that seems wrong or unfair."
- **True because:** the **reporting** half is built — `POST /questions/{id}/reports`, reporter
  always taken from the authenticated token
  ([questions.py](../apps/learning-api/src/learning_api/routers/questions.py), SPEC §5.8.7).
  ⚠️ The **challenging-a-result** half is **NOT BUILT and nowhere specified** — the phrase occurs
  exactly once in the entire SPEC, in this list. See §5.
- **Goes false if:** shipped as written today. The copy above deliberately promises only the half
  that exists.

---

## 3. Retention, which the notice must state (D-114 §4)

A standing obligation, carried since 2026-07-30 and reproduced here so it survives into the draft:

| what | window | on |
|---|---|---|
| tutor-chat messages | **90 days** | `created_at` ([tutor_chat_purge_cli.py](../apps/learning-api/src/learning_api/services/tutor_chat_purge_cli.py)) |
| derived facts (learning memory) | **90 days** | `last_confirmed_at` — a fact that keeps being reconfirmed stays |
| parent-visible reports | **365 days** | `created_at` — the deliberate exception, because a parent expects to re-open a report |

**And the sentence the notice must not contain**, in any paraphrase: that deleting a chat removes
everything derived from it. It does not. A fact consolidated into learning memory outlives the
message it came from, and stage narratives derived from the same tutoring data have their own
90-day clock. The notice should say what is kept and for how long, not imply an erasure the system
does not perform.

**Two windows exist that this table does not cover, and the drafter should know why.** Session
checkpoints are deleted on their own schedule — completed learning sessions at 30 days, abandoned
at 90, org Q&A threads at 180 (D-333). They are working state rather than a record a student would
recognise, and the 30/90 learning windows sit *inside* the 90-day figure above, so they do not
contradict it. The 180-day Q&A window belongs to `chat.intellichoice.org`, which this notice does
not cover — but the **Privacy Notice does**, and it should state it.

---

## 4. What the notice must not do

- **Substitute for parental consent** under 13 (§5.1.2, explicit).
- **Ask for a consent decision it cannot honour.** This is a notice. If a student cannot decline
  AI analysis and still use the product, do not present a checkbox that implies they can.
- **Name internal skill IDs or model names.** Student-facing language stays growth-oriented and
  age-appropriate; internal identifiers stay internal (SPEC §5.10.3).
- **Promise erasure.** See §3.
- **Disclose the three unbuilt behaviours as though they exist.** See §5.

---

## 5. What writing this found — three of eleven describe behaviour that does not exist

Checking each sentence against the system, rather than against the SPEC that lists it, is the only
part of this exercise that could fail. It did, three times:

1. **§2.11's "challenge learning results"** — the phrase appears **once in the whole SPEC**, in
   this very list, with no section defining it, no endpoint, and no UI. The reporting half is
   real; the challenging half is a right the product does not currently provide. **Either build a
   route for it or drop the clause** — a notice that grants a minor a right they cannot exercise
   is worse than one that stays quiet.
2. **§2.8's solution images** — S29 is deferred and not started (D-078), so there is no upload
   path. The disclosure describes a feature that does not exist. Ship the notice without it and
   add it with the feature, which its own "done when" already gates on a deletion test.
3. **§2.5's tutor and branch-manager sharing** — the roles exist and gate the Q&A corpus, but
   learning-api has no tutor- or manager-facing view of a student's record; the read half is
   deferred to integration (D-086/S43). Today the sentence is not true of this product.

**The recommendation is to ship eight, not eleven**, and to attach 2.5, 2.8 and 2.11 to the work
that makes each true. That keeps the notice accurate on day one, which is the only property it
really has to have. The alternative — disclosing all eleven because the SPEC lists eleven — states
things about a minor's data that are not the case.

**One wording note that is not a gap.** §2.10's SPEC line says data is "minimized and
de-identified where possible". The copy above keeps that hedge. It would be easy, and wrong, to
promise de-identification outright: the architecture makes it true for Postgres, logs, traces and
LLM payloads, and the org's MySQL system — outside this codebase — remains the source of truth for
real names and emails by design.

---

## 6. Owner and next step

**Owner: S45**, per D-127 §3's recommendation, with this file as the input it transcribes.
Counsel review of the resulting text remains a §6.1 launch gate. The three gaps in §5 need a
product decision before S45 starts, because they change how many disclosures there are.
