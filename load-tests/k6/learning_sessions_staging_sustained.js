// E1.1 (resume-evidence measurement program, MEASUREMENT_PLAN Theme 1) - the *sustained and
// repeated* sibling of `learning_sessions_staging.js`.
//
// **That script is not modified, and that is the whole point of this one being separate.** Its
// shape is the comparability baseline behind D-129/D-456: every staging learning number this
// repository has ever published came out of a `per-vu-iterations` run of it, and changing its
// executor would silently redefine what those numbers mean. So the flow, the per-step Trends and
// the anti-vacuity thresholds are copied here verbatim, and only the *executor* is new.
//
// Two weaknesses in the existing evidence this script exists to close (MEASUREMENT_PLAN Theme 1,
// "Weaknesses" 1 and 4):
//
//   1. **No harness in this repository has ever produced an RPS number.** Every scenario is
//      `per-vu-iterations`: each VU runs the flow once and the run ends. That measures latency
//      under a burst of N concurrent users; it says nothing about throughput the service can
//      hold, because the load disappears before a steady state exists. `SCENARIO=sustained`
//      uses `constant-vus` + `DURATION`, and `http_reqs` is thresholded so the rate is both
//      asserted and printed.
//   2. **Single-run p95s.** `SCENARIO=burst` reproduces the old shape exactly so it can be run
//      three times per level and reported as a median with a range, rather than one number
//      whose repeatability is unknown.
//
// **No model calls, by design.** Identical to the baseline script: k6 has no SSE support and
// never opens `/stream`, and `pre_intro` - the one Bedrock call on this journey - fires on SSE
// connect. So a sweep of this script costs $0 in model spend and its latency is database- and
// CPU-bound. (The SSE tiers of E1.2 are separate harnesses for exactly that reason.)
//
// **Documented ceiling, unchanged from the baseline:** staging seeds four students and only two
// are attendance-present (`student-ext-1`, `student-ext-4`), so VUs cycle over those two.
// Sessions are independent - checkpoint, assessment session and idempotency key are all
// per-session - so this is a valid *concurrency* measurement but not a ">100 distinct students"
// one. In `sustained` mode a VU runs the flow repeatedly, each iteration creating a fresh
// session, so the same caveat holds per iteration and nothing accumulates across them.
//
// Run:
//   make load-staging-learning-sustained VUS=25 SCENARIO=burst
//   make load-staging-learning-sustained VUS=25 SCENARIO=sustained DURATION=10m
// or through benchmarks/resume_evidence/01_platform/run_e1_sweep.sh, which does the whole sweep.

import http from "k6/http";
import { check, fail } from "k6";
import { Trend, Counter } from "k6/metrics";

const BASE_URL = __ENV.BASE_URL;
const SECRET = __ENV.STAGING_TOKEN_SECRET_LEARNING;
const VUS = parseInt(__ENV.VUS || "5", 10);
const SCENARIO = __ENV.SCENARIO || "burst";
const DURATION = __ENV.DURATION || "10m";
// Anti-vacuity floor, not a performance SLO. A run whose throughput collapses to near zero -
// every VU stuck on one request until `maxDuration` cuts it off - would otherwise report a
// flattering p95 over a handful of completed requests and "pass". The measured RPS is the
// deliverable; this only refuses to call a stalled run a measurement.
const MIN_RPS = parseFloat(__ENV.MIN_RPS || "1");
// A sustained run's first seconds are not the steady state it exists to measure: connections
// are being established, the ALB is still warming its targets, and every session in flight is
// the first one its replica has seen. Requests are tagged `phase=cold` for this many ms after
// the scenario starts and `phase=warm` after, which turns the summary's submetrics into a
// cold/warm split with no per-request output file to store. A burst run has no steady state to
// separate, so it defaults to 0 and everything is `warm`.
const COLD_MS = parseInt(__ENV.COLD_MS || (SCENARIO === "sustained" ? "60000" : "0"), 10);
// The deployed `intellichoice-staging-learning-api-p95-latency` alarm's own number, kept for
// comparability with the baseline script. Expected to breach at the top of the sweep (D-456
// measured warm p95 3.03 s at 25 VUs) - that is a *result*, not a harness failure, so the sweep
// runner records a breach and continues. Only the error-rate and anti-vacuity thresholds are
// stop conditions.
const P95_MS = parseInt(__ENV.P95_MS || "3000", 10);

const PRESENT_STUDENTS = ["student-ext-1", "student-ext-4"];

const tokenTrend = new Trend("learning_dev_token", true);
const createTrend = new Trend("learning_create_session", true);
const studentTrend = new Trend("learning_select_student", true);
const topicTrend = new Trend("learning_select_topic", true);
const answerTrend = new Trend("learning_answer", true);
const flowTrend = new Trend("learning_flow_total", true);
const blockedCounter = new Counter("learning_attendance_blocked");
const answersSubmitted = new Counter("learning_answers_submitted");
// Counted separately from `http_req_failed` so the report can say *which* failures happened.
// A 5xx is a stop condition for the sweep (a possible D-455 rotation-class incident); a 4xx is
// usually a fixture or auth problem and means something different.
const status4xx = new Counter("learning_status_4xx");
const status5xx = new Counter("learning_status_5xx");

const SCENARIOS = {
  // The baseline script's shape, unchanged: N concurrent users each run the flow once.
  burst: {
    executor: "per-vu-iterations",
    vus: VUS,
    iterations: 1,
    maxDuration: __ENV.MAX_DURATION || "10m",
  },
  // The new one: N concurrent users keep running the flow for DURATION, so the service reaches
  // and holds a steady state and `http_reqs` becomes a meaningful rate.
  sustained: {
    executor: "constant-vus",
    vus: VUS,
    duration: DURATION,
    // Let an iteration that started before the clock ran out finish, rather than reporting it
    // as interrupted and dropping its requests from the denominator.
    gracefulStop: __ENV.GRACEFUL_STOP || "60s",
  },
};

if (!SCENARIOS[SCENARIO]) {
  throw new Error(`SCENARIO must be one of ${Object.keys(SCENARIOS).join(", ")}, got '${SCENARIO}'`);
}

export const options = {
  scenarios: { learning_flow: SCENARIOS[SCENARIO] },
  thresholds: {
    http_req_failed: ["rate<0.01"],
    http_req_duration: [`p(95)<${P95_MS}`],
    // Both copied from the baseline script: a run where every VU was attendance-gated, or
    // reached the exam and answered nothing, would post excellent latency and measure nothing.
    learning_attendance_blocked: ["count==0"],
    learning_answers_submitted: ["count>0"],
    // The number this script exists to produce.
    http_reqs: [`rate>${MIN_RPS}`],
    // Not assertions - k6 only materializes a submetric in the summary if a threshold names it,
    // so these exist to *export* the cold/warm split. The bounds are deliberately unreachable so
    // a slow cold window can never be mistaken for a failed run.
    "http_req_duration{phase:cold}": ["p(95)<3600000"],
    "http_req_duration{phase:warm}": ["p(95)<3600000"],
    "http_reqs{phase:cold}": ["count>=0"],
    "http_reqs{phase:warm}": ["count>=0"],
  },
};

function authHeaders(token, extra, phase) {
  return {
    headers: Object.assign(
      { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      extra || {},
    ),
    tags: { phase },
  };
}

function recordStatus(res) {
  if (res.status >= 500) status5xx.add(1);
  else if (res.status >= 400) status4xx.add(1);
}

export function setup() {
  if (!BASE_URL) fail("BASE_URL is required (the learning CloudFront domain)");
  if (!SECRET) {
    fail(
      "STAGING_TOKEN_SECRET_LEARNING is required - /dev/token is secret-gated on staging " +
        "(D-097) and returns 404 without the header. Use `make load-staging-learning-sustained`.",
    );
  }
  // Handed to every VU so the cold/warm boundary is one clock for the whole run, not each VU's
  // own first iteration.
  return { startedAt: Date.now() };
}

export default function (data) {
  const phase = Date.now() - data.startedAt < COLD_MS ? "cold" : "warm";
  // `__VU` is stable across iterations, so in `sustained` mode a VU keeps its student for the
  // whole run. Both fixtures stay in rotation either way.
  const sub = PRESENT_STUDENTS[(__VU - 1) % PRESENT_STUDENTS.length];
  const flowStart = Date.now();

  // k6 omits a metric that never took a sample, so a clean run would export *no*
  // `learning_status_5xx` key at all - indistinguishable, to a parser, from a harness that
  // forgot to count. Seeding zero makes "no 5xx" an assertable 0 rather than an absence.
  status4xx.add(0);
  status5xx.add(0);

  // The secret rides in a header, never in a URL or a log line: a 200 body here *is* a
  // credential, so nothing below echoes a response body on failure either.
  const tokenRes = http.post(
    `${BASE_URL}/dev/token`,
    JSON.stringify({ role: "student", sub }),
    {
      headers: { "Content-Type": "application/json", "X-Staging-Token-Secret": SECRET },
      tags: { phase },
    },
  );
  tokenTrend.add(tokenRes.timings.duration);
  recordStatus(tokenRes);
  if (!check(tokenRes, { "dev-token 200": (r) => r.status === 200 })) {
    // Not `fail()`: in `sustained` mode `fail` aborts the whole VU for the rest of the run, so
    // one intermittent `/dev/token` through CloudFront would quietly shrink the concurrency
    // being measured. The check above already counts it, and the request is in `http_req_failed`.
    return;
  }
  const token = tokenRes.json("token");
  const opts = authHeaders(token, null, phase);

  const createRes = http.post(`${BASE_URL}/learning/sessions`, null, opts);
  createTrend.add(createRes.timings.duration);
  recordStatus(createRes);
  check(createRes, { "create session 200": (r) => r.status === 200 });
  const sessionId = createRes.json("learning_session_id");
  if (!sessionId) return;

  const studentRes = http.post(
    `${BASE_URL}/learning/sessions/${sessionId}/student`,
    JSON.stringify({ student_id: sub }),
    opts,
  );
  studentTrend.add(studentRes.timings.duration);
  recordStatus(studentRes);
  check(studentRes, { "select student 200": (r) => r.status === 200 });

  const topicRes = http.post(
    `${BASE_URL}/learning/sessions/${sessionId}/topics`,
    JSON.stringify({ topic_id: "linear_equations" }),
    opts,
  );
  topicTrend.add(topicRes.timings.duration);
  recordStatus(topicRes);
  check(topicRes, { "select topic 200": (r) => r.status === 200 });
  if (topicRes.status !== 200) return;

  // `phase: "blocked"` is the attendance gate doing its job - correct behaviour, but it means
  // this VU never reached an exam, so the run must not silently count as a pass.
  if (topicRes.json("phase") === "blocked") {
    blockedCounter.add(1);
    return;
  }

  const items = topicRes.json("items") || [];
  for (const item of items) {
    const answerRes = http.post(
      `${BASE_URL}/learning/sessions/${sessionId}/answers`,
      JSON.stringify({
        question_variant_id: item.question_variant_id,
        selected_option: "a",
        response_time_ms: 2000,
      }),
      authHeaders(token, {
        // Per-session, so two VUs sharing a student never collide, and so do two iterations of
        // the same VU in `sustained` mode - each iteration has its own session id.
        "Idempotency-Key": `${sessionId}-${item.question_variant_id}`,
      }, phase),
    );
    answerTrend.add(answerRes.timings.duration);
    recordStatus(answerRes);
    if (check(answerRes, { "answer 200": (r) => r.status === 200 })) {
      answersSubmitted.add(1);
    }
  }

  flowTrend.add(Date.now() - flowStart);
}
