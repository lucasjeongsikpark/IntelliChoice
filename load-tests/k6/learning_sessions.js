// S34 / SPEC §6.23: "more than 100 concurrent learning sessions" scenario.
//
// Each VU is one distinct student (loadtest-student-${__VU}, seeded by
// ../loadtest_fixtures.py) running the real deterministic pre-exam flow end to end
// exactly ONCE: dev-token -> create session -> select self -> select topic (pre-exam
// gate) -> answer every returned item. `per-vu-iterations`/`iterations: 1` is
// deliberate, not `constant-vus` - SPEC's target is ">100 *concurrent sessions*" (a
// concurrency snapshot: this many distinct students mid-flow at once), not a sustained
// requests/sec throughput target. An earlier `constant-vus` version of this script
// re-ran the whole flow (including re-minting a token) in a tight loop with no pacing
// and produced ~6,500 req/s against a 150-VU run - unrepresentative of how a real
// student uses the app, and it also self-tripped the S33/D-087 global per-IP rate
// limiter (see DECISIONS.md's S34 entry for the real finding that came out of that:
// even a *realistic* one-shot 150-concurrent-session burst from one shared branch IP
// gets meaningfully close to the limiter's original default).
//
// This is a local-concurrency proxy for the real >1,000-student target (see
// ../README.md) - it exercises the same async FastAPI process, connection pool, and
// LangGraph checkpoint path a real deployment would, just at local-machine scale, not
// staging/production scale.
//
// Run (see ../README.md for the full docker command):
//   docker run --rm -i -e BASE_URL=http://host.docker.internal:8001 -e VUS=150 \
//     grafana/k6 run - < k6/learning_sessions.js

import http from "k6/http";
import { check, fail } from "k6";

const BASE_URL = __ENV.BASE_URL || "http://localhost:8001";
const VUS = parseInt(__ENV.VUS || "150", 10);

export const options = {
  scenarios: {
    concurrent_learning_sessions: {
      executor: "per-vu-iterations",
      vus: VUS,
      iterations: 1,
      maxDuration: "2m",
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.01"],
    // SPEC §5.33.4: "General API P95 near one second".
    http_req_duration: ["p(95)<1000"],
  },
};

function studentId() {
  return `loadtest-student-${__VU}`;
}

function authHeaders(token) {
  return { headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" } };
}

export default function () {
  const sub = studentId();

  const tokenRes = http.post(
    `${BASE_URL}/dev/token`,
    JSON.stringify({ role: "student", sub, audience: "learning" }),
    { headers: { "Content-Type": "application/json" } }
  );
  if (!check(tokenRes, { "dev-token 200": (r) => r.status === 200 })) {
    fail(`dev/token failed: ${tokenRes.status} ${tokenRes.body}`);
  }
  const token = tokenRes.json("token");
  const opts = authHeaders(token);

  const createRes = http.post(`${BASE_URL}/learning/sessions`, null, opts);
  check(createRes, { "create session 200": (r) => r.status === 200 });
  const sessionId = createRes.json("learning_session_id");

  const selectStudentRes = http.post(
    `${BASE_URL}/learning/sessions/${sessionId}/student`,
    JSON.stringify({ student_id: sub }),
    opts
  );
  check(selectStudentRes, { "select student 200": (r) => r.status === 200 });

  const topicRes = http.post(
    `${BASE_URL}/learning/sessions/${sessionId}/topics`,
    JSON.stringify({ topic_id: "linear_equations" }),
    opts
  );
  const topicOk = check(topicRes, {
    "select topic 200": (r) => r.status === 200,
    "items or pending_interrupt present": (r) => {
      const body = r.json();
      return body.items !== null || body.pending_interrupt !== null;
    },
  });
  if (!topicOk) {
    return;
  }

  const items = topicRes.json("items") || [];
  for (const item of items) {
    const idemKey = `${sub}-${sessionId}-${item.question_variant_id}`;
    const answerRes = http.post(
      `${BASE_URL}/learning/sessions/${sessionId}/answers`,
      JSON.stringify({
        question_variant_id: item.question_variant_id,
        selected_option: "a",
        response_time_ms: 2000,
      }),
      {
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
          "Idempotency-Key": idemKey,
        },
      }
    );
    check(answerRes, { "answer 200": (r) => r.status === 200 });
  }
}
