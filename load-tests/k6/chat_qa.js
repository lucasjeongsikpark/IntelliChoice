// S34 / SPEC §6.23: concurrent chat-api RAG Q&A load, and one of the "concurrent Bedrock
// requests" scenarios (the local dev server runs MockBedrockProvider by default - see
// ../README.md for what this does and doesn't prove about real Bedrock concurrency).
//
// Each VU is one distinct student (loadtest-student-${__VU}, seeded by
// ../loadtest_fixtures.py, same rows the learning scenario uses - chat-api only reads the
// MySQL `users` row for role/branch resolution, never writes to it). Query text uses the
// "zqxv" nonsense-marker convention (D-018/D-090) so it can never spuriously match real
// seeded knowledge-content and produce a misleading grounded answer under load.
//
// Run (see ../README.md for the full docker command):
//   docker run --rm -i -e BASE_URL=http://host.docker.internal:8002 -e VUS=150 \
//     grafana/k6 run - < k6/chat_qa.js

import http from "k6/http";
import { check, fail } from "k6";

const BASE_URL = __ENV.BASE_URL || "http://localhost:8002";
const VUS = parseInt(__ENV.VUS || "150", 10);

export const options = {
  scenarios: {
    concurrent_chat_qa: {
      executor: "per-vu-iterations",
      vus: VUS,
      iterations: 1,
      maxDuration: "2m",
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<1000"],
  },
};

export default function () {
  const sub = `loadtest-student-${__VU}`;

  const tokenRes = http.post(
    `${BASE_URL}/dev/token`,
    JSON.stringify({ role: "student", sub, audience: "chat" }),
    { headers: { "Content-Type": "application/json" } }
  );
  if (!check(tokenRes, { "dev-token 200": (r) => r.status === 200 })) {
    fail(`dev/token failed: ${tokenRes.status} ${tokenRes.body}`);
  }
  const token = tokenRes.json("token");
  const opts = {
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
  };

  const createRes = http.post(`${BASE_URL}/chat/sessions`, null, opts);
  check(createRes, { "create chat session 200": (r) => r.status === 200 });
  const sessionId = createRes.json("chat_session_id");

  const messageRes = http.post(
    `${BASE_URL}/chat/sessions/${sessionId}/messages`,
    JSON.stringify({ query: `zqxv load test query from vu ${__VU} iter ${__ITER}` }),
    opts
  );
  check(messageRes, { "message 200": (r) => r.status === 200 });
}
