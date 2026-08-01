// S43 / §2.6 criterion 7: the *live-staging* leg of the chat load threshold - real
// CloudFront edge, real ALB, real ECS tasks, real Bedrock, real corpus.
//
// This does NOT replace `chat_qa.js`, and the two thresholds are deliberately different
// numbers measuring different things (D-115 §11):
//
//   chat_qa.js          local server, MockBedrockProvider, deliberately non-matching
//                       "zqxv" queries -> the application's own overhead with no model
//                       in the path. p(95) < 1000 is correct for that and stays.
//   chat_qa_staging.js  this file. A *grounded* turn against the deployed stack, which is
//                       four sequential model calls (scope_and_intent -> embedding ->
//                       rerank -> rag_answer). It cannot be under ~8s by construction.
//
// Why k6 and not a script: D-115 §12 spent two measurement rounds establishing that
// 5-6 client-side ReadTimeout/ReadErrors per run were the ad-hoc driver's own connection
// pooling, not a server or edge failure - the ALB reported zero errors of every category
// in every run and the app answered 100% 200. A naive pooled client can see a reset on a
// 10-17s request through CloudFront where a browser or k6 retries. So criterion 7's
// error-rate leg is measured here, with a client whose failure modes are not its own.
//
// Guest turns, so no secrets and nothing to leak into a CI log: SPEC §5.19.1 makes
// anonymous chat access valid and `POST /chat/sessions` takes optional claims. This is
// also exactly how D-115's before/after numbers were measured, so the comparison holds.
//
// Run (staging chat CloudFront domain - same-origin, so the web URL is the API URL):
//   docker run --rm -i -e BASE_URL=https://d222glidpp4azv.cloudfront.net \
//     grafana/k6 run - < load-tests/k6/chat_qa_staging.js
//
// Or `make load-staging-chat`.

import http from "k6/http";
import { check, fail } from "k6";
import { Counter, Trend } from "k6/metrics";

const BASE_URL = __ENV.BASE_URL;
if (!BASE_URL) {
  fail("BASE_URL is required - this scenario has no localhost default on purpose.");
}

// Concurrency 5 and ~70 turns match D-115's measurement, so a run here is comparable to
// the numbers the 20s threshold was derived from rather than a different experiment.
const VUS = parseInt(__ENV.VUS || "5", 10);
const ITERATIONS = parseInt(__ENV.ITERATIONS || "14", 10);

// The turn's own latency, separate from `http_req_duration`, which would otherwise be
// diluted by the near-instant session-create call and report a flattering p95.
const turnDuration = new Trend("chat_turn_duration", true);
// A refusal returns 200 in tens of milliseconds. Counting them matters because they make
// the latency numbers *better*: nine such turns in 114 were the visible face of the
// circuit breaker tripping in D-113/AUD-X-10, and a p95 computed over them is a lie.
const fastRefusals = new Counter("chat_fast_refusals");
const answered = new Counter("chat_answered_turns");

export const options = {
  scenarios: {
    grounded_chat_turns: {
      executor: "per-vu-iterations",
      vus: VUS,
      iterations: ITERATIONS,
      maxDuration: "15m",
    },
  },
  thresholds: {
    // Criterion 7's live-staging thresholds (user decision, S43). 20s is the measured
    // p95 of ~16s plus 25% headroom; it is the same number the chat-api paging alarm
    // moved to in AUD-X-13, set once from one measurement.
    "chat_turn_duration": ["p(95)<20000"],
    "http_req_failed": ["rate<0.01"],
    // Not a latency assertion: a run whose p95 passes *because* turns refused instantly
    // has measured nothing. Zero is the post-D-115 observation (0 of 74).
    "chat_fast_refusals": ["count==0"],
  },
  // Escape hatch for re-testing D-115 §12's pooled-connection finding against k6 itself.
  // Left off by default: k6 retrying a reset is the behaviour that makes it the right
  // instrument here, and turning reuse off would hide the thing worth knowing.
  noConnectionReuse: (__ENV.NO_CONNECTION_REUSE || "false") === "true",
};

// Questions the deployed corpus can actually answer *today*. Widened 2026-08-01 per this
// file's own standing note - but by ONE question, not the six the note expected, because
// every candidate was verified against live staging first and only one grounds:
//   - "How do I become a volunteer tutor?" answers with a public-volunteer-guide citation.
//   - Four other newly-effective public documents (student-participation-guide,
//     privacy-notice, ai-use-notice, contact-guide) return the no-source refusal even for
//     near-verbatim wording ("Where do student records live?"), while the same corpus
//     answers them locally - a staging corpus gap, filed as a finding on 2026-08-01, not a
//     question-wording problem. Add their questions when it is fixed.
//   - Anything enrollment-shaped stays out: public-enrollment-faq is the only document
//     covering it and it is status `draft`, so the filter refuses it by design (D-112).
// A refusal is a different, much faster code path than the grounded turn criterion 7
// measures, so unverified questions would poison the p95 this file exists to read.
const QUESTIONS = [
  "What are the Saturday hours?",
  "Where are your branches located?",
  "Who is on the leadership team?",
  "What is IntelliChoice?",
  "When does the fall term start?",
  "How do I become a volunteer tutor?",
];

export default function () {
  const question = QUESTIONS[(__VU + __ITER) % QUESTIONS.length];
  const opts = {
    headers: { "Content-Type": "application/json" },
    timeout: "90s",
  };

  // A fresh session per turn, matching how D-115 measured: no conversation history means
  // no growing payload, so every turn in the run is the same unit of work.
  const createRes = http.post(`${BASE_URL}/chat/sessions`, null, opts);
  if (!check(createRes, { "create chat session 200": (r) => r.status === 200 })) {
    fail(`create session failed: ${createRes.status}`);
  }
  const sessionId = createRes.json("chat_session_id");

  const messageRes = http.post(
    `${BASE_URL}/chat/sessions/${sessionId}/messages`,
    JSON.stringify({ query: question }),
    opts
  );
  turnDuration.add(messageRes.timings.duration);

  check(messageRes, { "message 200": (r) => r.status === 200 });

  // Below one second, no model was called: either the circuit breaker is open or the turn
  // refused on scope. Both are findings, and neither should count as a fast healthy turn.
  if (messageRes.status === 200 && messageRes.timings.duration < 1000) {
    fastRefusals.add(1);
  } else if (messageRes.status === 200) {
    answered.add(1);
  }
}
