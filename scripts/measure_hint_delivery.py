"""Does a real student on staging, who waits, see a personalized hint? (D-334)

Measured 2026-08-15: **2 of 4 runs delivered**, which is the ~50% the in-process
`SessionEventBus` predicts across `learning-api`'s two ECS tasks. Kept as a script rather than
a test because it needs real staging, a real token and real Bedrock spend (~1.5c/run).

Usage:
    AWS_PROFILE=... LEARNING_BASE=https://<edge> \\
      STAGING_TOKEN_SECRET=$(aws secretsmanager get-secret-value --secret-id \\
        intellichoice-staging/learning-api/staging-token-shared-secret \\
        --query SecretString --output text) \\
      uv run python scripts/measure_hint_delivery.py

Holds an SSE connection open across the hint request and watches for a snapshot whose hint text
differs from the canonical rung the student was served instantly.

**Why an SSE connection is required.** The scheduler deliberately does not write the checkpoint
(D-272), so the personalized hint reaches the client *only* over the event bus. A GET after the
fact would show the canonical rung and prove nothing.

Read-mostly, but it does drive one real session and spends a few cents of Bedrock.
Never prints the token or the secret.
"""

import asyncio
import json
import os
import sys

import httpx

BASE = os.environ["LEARNING_BASE"]
SECRET = os.environ["STAGING_TOKEN_SECRET"]
STUDENT = os.environ.get("PROBE_STUDENT", "student-ext-1")
WAIT_S = float(os.environ.get("PROBE_WAIT_S", "25"))


async def main() -> int:
    async with httpx.AsyncClient(base_url=BASE, timeout=60.0) as c:
        r = await c.post(
            "/dev/token",
            headers={"X-Staging-Token-Secret": SECRET},
            json={"role": "student", "sub": STUDENT},
        )
        if r.status_code != 200:
            print(f"PROBE | token failed {r.status_code}")
            return 1
        token = r.json()["token"]
        h = {"Authorization": f"Bearer {token}"}

        sid = (await c.post("/learning/sessions", headers=h)).json()["learning_session_id"]
        print(f"PROBE | session {sid}", flush=True)
        await c.post(f"/learning/sessions/{sid}/student", headers=h, json={"student_id": STUDENT})
        body = (
            await c.post(
                f"/learning/sessions/{sid}/topics", headers=h, json={"topic_id": "linear_equations"}
            )
        ).json()
        if "items" not in body:
            print(f"PROBE | no items: {json.dumps(body)[:200]}")
            return 1

        # Pre-exam: answer everything with option 'a'. Correctness does not matter here; reaching
        # the study loop does.
        for i, item in enumerate(body["items"]):
            await c.post(
                f"/learning/sessions/{sid}/answers",
                headers={**h, "Idempotency-Key": f"probe-pre-{i}"},
                json={
                    "question_variant_id": item["question_variant_id"],
                    "selected_option": "a",
                    "response_time_ms": 1200,
                },
            )
        body = (await c.post(f"/learning/sessions/{sid}/exam/finalize", headers=h, json={})).json()
        print(f"PROBE | phase after finalize: {body.get('phase')}", flush=True)
        if body.get("phase") != "study":
            return 1

        # Open the SSE stream BEFORE asking for the hint, so nothing published can be missed.
        received: list[dict] = []

        async def listen() -> None:
            # `token` is a QUERY parameter here, not an Authorization header - the stream is
            # opened by EventSource, which cannot set headers. Passing it as a header returned a
            # 422 that the first version of this probe never looked at, so it reported
            # "not delivered" on the strength of zero frames. Status is printed now.
            async with c.stream(
                "GET",
                f"/learning/sessions/{sid}/stream",
                params={"token": token},
                timeout=None,
            ) as resp:
                print(f"PROBE | stream status={resp.status_code}", flush=True)
                if resp.status_code != 200:
                    return
                async for line in resp.aiter_lines():
                    if line.startswith("data:"):
                        try:
                            received.append(json.loads(line[5:].strip()))
                        except json.JSONDecodeError:
                            pass

        task = asyncio.create_task(listen())
        await asyncio.sleep(3)

        # Answer the study question wrong to open the intervention choice.
        item = body["items"][0]
        variant = item["question_variant_id"]
        wrong = next(
            o for o in ("a", "b", "c", "d") if o != str(item.get("correct_option", "")).lower()
        )
        ans = (
            await c.post(
                f"/learning/sessions/{sid}/answers",
                headers={**h, "Idempotency-Key": "probe-study-0"},
                json={
                    "question_variant_id": variant,
                    "selected_option": wrong,
                    "response_time_ms": 3000,
                },
            )
        ).json()
        pending = ans.get("pending_interrupt") or {}
        print(
            f"PROBE | study answer is_correct={ans.get('is_correct')} "
            f"interrupt={pending.get('interrupt_type')}",
            flush=True,
        )
        if pending.get("interrupt_type") != "intervention_choice":
            print("PROBE | no intervention interrupt - answered correctly by luck; inconclusive")
            task.cancel()
            return 2

        hint = (
            await c.post(
                f"/learning/sessions/{sid}/respond",
                headers=h,
                json={"interrupt_type": "intervention_choice", "choice": "hint"},
            )
        ).json()
        served = (hint.get("intervention") or {}).get("hint_text", "")
        print(f"PROBE | served hint: {served[:90]!r}", flush=True)

        # The whole point: wait, like a student reading, instead of clicking on.
        print(f"PROBE | holding the stream for {WAIT_S}s without answering...", flush=True)
        await asyncio.sleep(WAIT_S)
        task.cancel()

        hints_seen = [
            (e.get("intervention") or {}).get("hint_text")
            for e in received
            if (e.get("intervention") or {}).get("hint_text")
        ]
        print(f"PROBE | sse frames={len(received)} frames_with_hint={len(hints_seen)}", flush=True)
        different = [t for t in hints_seen if t and t != served]
        if different:
            print(f"PROBE | RESULT=DELIVERED personalized={different[-1][:120]!r}")
            return 0
        if not received:
            print("PROBE | RESULT=INCONCLUSIVE - zero SSE frames, so the probe measured nothing")
            return 4
        print("PROBE | RESULT=NOT_DELIVERED (frames arrived; none carried a differing hint)")
        return 3


sys.exit(asyncio.run(main()))
