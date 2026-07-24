"""S34 / SPEC §6.23: "more than 100 SSE connections" scenario.

k6 has no native SSE support (its HTTP client fully buffers a response rather than
streaming it), so this is a plain asyncio/httpx script instead - same "reach for a direct
script over forcing the wrong tool" precedent as the project's own live-verification
scripts (D-034). Opens `--count` concurrent `GET .../stream` connections (the real
`EventSource`-shaped endpoint, `?token=` auth per D-032, not `Authorization` - see
`routers/stream.py`'s own docstring), holds each open for `--hold-seconds`, and reports how
many connected successfully, received at least one event (the initial snapshot every
(re)connect gets per `routers/stream.py`), and how many dropped early.

Needs `--count` learning sessions to already exist with a student selected (topic
selection not required - the initial snapshot fires on connect regardless of phase). This
script creates its own sessions first using the same loadtest-student-N rows
`loadtest_fixtures.py` seeds.

Run: uv run python load-tests/sse_load.py --count 150 --hold-seconds 30
"""

import argparse
import asyncio
import time

import httpx

DEFAULT_BASE_URL = "http://localhost:8001"


async def _create_session(client: httpx.AsyncClient, base_url: str, n: int) -> tuple[str, str]:
    sub = f"loadtest-student-{n}"
    token_res = await client.post(
        f"{base_url}/dev/token", json={"role": "student", "sub": sub, "audience": "learning"}
    )
    token_res.raise_for_status()
    token = token_res.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    create_res = await client.post(f"{base_url}/learning/sessions", headers=headers)
    create_res.raise_for_status()
    session_id = create_res.json()["learning_session_id"]

    select_res = await client.post(
        f"{base_url}/learning/sessions/{session_id}/student",
        json={"student_id": sub},
        headers=headers,
    )
    select_res.raise_for_status()

    return session_id, token


async def _hold_stream(
    base_url: str, session_id: str, token: str, hold_seconds: float
) -> dict[str, bool | float]:
    url = f"{base_url}/learning/sessions/{session_id}/stream?token={token}"
    connected = False
    received_event = False
    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("GET", url) as response:
                connected = response.status_code == 200
                if not connected:
                    return {"connected": False, "received_event": False, "duration_s": 0.0}
                deadline = start + hold_seconds
                async for line in response.aiter_lines():
                    if line.startswith("data:"):
                        received_event = True
                    if time.monotonic() >= deadline:
                        break
    except (httpx.ReadTimeout, httpx.RemoteProtocolError, httpx.ConnectError):
        pass
    return {
        "connected": connected,
        "received_event": received_event,
        "duration_s": time.monotonic() - start,
    }


async def main(base_url: str, count: int, hold_seconds: float) -> None:
    async with httpx.AsyncClient(timeout=30.0) as client:
        print(f"Creating {count} learning sessions...")
        sessions = await asyncio.gather(
            *(_create_session(client, base_url, i) for i in range(1, count + 1))
        )
    print(f"Opening {count} concurrent SSE connections, holding {hold_seconds}s each...")
    results = await asyncio.gather(
        *(
            _hold_stream(base_url, session_id, token, hold_seconds)
            for session_id, token in sessions
        )
    )

    connected = sum(1 for r in results if r["connected"])
    received = sum(1 for r in results if r["received_event"])
    print(f"Connected: {connected}/{count}")
    print(f"Received >=1 event: {received}/{count}")
    if connected < count:
        print("WARNING: not all connections succeeded - see exceptions above.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--count", type=int, default=150)
    parser.add_argument("--hold-seconds", type=float, default=30.0)
    args = parser.parse_args()
    asyncio.run(main(args.base_url, args.count, args.hold_seconds))
