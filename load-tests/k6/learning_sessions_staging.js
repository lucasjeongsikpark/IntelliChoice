// S43 continuation / §2.6 criterion 7's **learning-app leg** — the half that was still
// unmeasured after D-116 closed the chat leg (p95 16.68 s, 0 errors, 3 tasks).
//
// Distinct from k6/learning_sessions.js, which drives the same flow against the local
// docker-compose stack as a >100-concurrent-session proxy. This one runs against the
// deployed stack through the real CloudFront edge, so it measures the real ALB, RDS and
// Fargate task sizing. Read this header before comparing the two scripts' numbers.
//
// **This flow makes no model calls, and that is the point of measuring it separately from
// chat.** A grounded chat turn is four sequential Bedrock calls (hence the 20 s threshold
// D-116 set for it); the learning pre-exam path is deterministic — attendance gating,
// question selection, grading, checkpoint writes (SPEC §5.0's "deterministic core"). The
// one model call on this journey, `pre_intro`, fires on **SSE connect**, and k6 has no SSE
// support and does not open the stream — so this run is essentially free and its latency is
// database- and CPU-bound. That is also why learning-api kept the 3 s paging threshold when
// chat-api moved to 20 s (AUD-X-13).
//
// **Threshold: p95 < 3 s, errors < 1%.** The error rate is criterion 7's own decided leg
// (D-116 §1). The 3 s is *not* a fresh guess — it is the number the deployed
// `intellichoice-staging-learning-api-p95-latency` alarm already pages on, so a run that
// stays under it is asserting exactly the operational promise the environment makes about
// itself. Same "one number, two places" reasoning D-116 used for chat, in the direction
// that reuses an existing decision rather than inventing a parallel one.
//
// **Documented ceiling: staging seeds four students and only two are attendance-present**
// (`student-ext-1`, `student-ext-4`; `student-ext-2` is absent and `student-ext-3` has no
// row, so both are correctly gated out of an exam by SPEC §5.4.4). VUs therefore cycle over
// those two rather than getting one student each. Sessions are independent — the graph
// checkpoint, the assessment session and the idempotency key are all per-session — so this
// is a valid concurrency measurement, but it is *not* the ">100 distinct students" shape
// SPEC §6.23 asks for. Reaching that on staging needs more seeded fixtures and is its own
// exercise; see load-tests/README.md.
//
// Run: `make load-staging-learning` (fetches the token secret from Secrets Manager).

import http from "k6/http";
import { check, fail } from "k6";
import { Trend, Counter } from "k6/metrics";

const BASE_URL = __ENV.BASE_URL;
const SECRET = __ENV.STAGING_TOKEN_SECRET_LEARNING;
const VUS = parseInt(__ENV.VUS || "5", 10);

// The two attendance-present fixtures. See the header for why this list is short.
const PRESENT_STUDENTS = ["student-ext-1", "student-ext-4"];

// Per-step trends, because a single aggregate p95 over a flow whose steps differ by an
// order of magnitude tells you nothing about which step to fix - the mistake D-116 had to
// correct on the chat scenario, where a cheap session-create call flattered the p95.
const tokenTrend = new Trend("learning_dev_token", true);
const createTrend = new Trend("learning_create_session", true);
const studentTrend = new Trend("learning_select_student", true);
const topicTrend = new Trend("learning_select_topic", true);
const answerTrend = new Trend("learning_answer", true);
const flowTrend = new Trend("learning_flow_total", true);
const blockedCounter = new Counter("learning_attendance_blocked");
const answersSubmitted = new Counter("learning_answers_submitted");

export const options = {
  scenarios: {
    concurrent_learning_sessions: {
      executor: "per-vu-iterations",
      vus: VUS,
      iterations: 1,
      // 10m, not 5m: at the criterion's 150 concurrent each VU's 14-request flow takes far
      // longer than the ~11s it does at 5, and a run cut off by `maxDuration` reports
      // interrupted iterations and measures nothing useful.
      maxDuration: __ENV.MAX_DURATION || "10m",
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<3000"],
    // A run where every VU is attendance-gated would post near-zero latency and "pass"
    // while never reaching an exam. Fail instead: the gate firing on a *present* student is
    // either a stale weekly fixture (AUD-F-20) or a real regression, and both matter.
    learning_attendance_blocked: ["count==0"],
    // Likewise, a run that reaches the exam and answers nothing is not a measurement.
    learning_answers_submitted: ["count>0"],
  },
};

function authHeaders(token, extra) {
  return {
    headers: Object.assign(
      { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      extra || {},
    ),
  };
}

export function setup() {
  if (!BASE_URL) fail("BASE_URL is required (the learning CloudFront domain)");
  if (!SECRET) {
    fail(
      "STAGING_TOKEN_SECRET_LEARNING is required - /dev/token is secret-gated on staging " +
        "(D-097) and returns 404 without the header. Use `make load-staging-learning`.",
    );
  }
}

export default function () {
  const sub = PRESENT_STUDENTS[(__VU - 1) % PRESENT_STUDENTS.length];
  const flowStart = Date.now();

  // The secret rides in a header, never in a URL or a log line: a 200 body here *is* a
  // credential, so nothing below echoes a response body on failure either.
  const tokenRes = http.post(
    `${BASE_URL}/dev/token`,
    JSON.stringify({ role: "student", sub }),
    { headers: { "Content-Type": "application/json", "X-Staging-Token-Secret": SECRET } },
  );
  tokenTrend.add(tokenRes.timings.duration);
  if (!check(tokenRes, { "dev-token 200": (r) => r.status === 200 })) {
    fail(`dev/token failed with ${tokenRes.status} (404 means the secret was not accepted)`);
  }
  const token = tokenRes.json("token");
  const opts = authHeaders(token);

  const createRes = http.post(`${BASE_URL}/learning/sessions`, null, opts);
  createTrend.add(createRes.timings.duration);
  check(createRes, { "create session 200": (r) => r.status === 200 });
  const sessionId = createRes.json("learning_session_id");
  if (!sessionId) return;

  const studentRes = http.post(
    `${BASE_URL}/learning/sessions/${sessionId}/student`,
    JSON.stringify({ student_id: sub }),
    opts,
  );
  studentTrend.add(studentRes.timings.duration);
  check(studentRes, { "select student 200": (r) => r.status === 200 });

  const topicRes = http.post(
    `${BASE_URL}/learning/sessions/${sessionId}/topics`,
    JSON.stringify({ topic_id: "linear_equations" }),
    opts,
  );
  topicTrend.add(topicRes.timings.duration);
  check(topicRes, { "select topic 200": (r) => r.status === 200 });
  if (topicRes.status !== 200) return;

  // `phase: "blocked"` is the attendance gate doing its job - correct behaviour, but it
  // means this VU never reached an exam, so the run must not silently count as a pass.
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
        // Per-session, so two VUs sharing a student never collide (see the header).
        "Idempotency-Key": `${sessionId}-${item.question_variant_id}`,
      }),
    );
    answerTrend.add(answerRes.timings.duration);
    if (check(answerRes, { "answer 200": (r) => r.status === 200 })) {
      answersSubmitted.add(1);
    }
  }

  flowTrend.add(Date.now() - flowStart);
}
