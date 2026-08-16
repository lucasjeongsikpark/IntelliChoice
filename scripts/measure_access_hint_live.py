"""Does the access hint fire when it should, and stay silent when it should? (D-351)

D-343 found one case live: a guest asking about the parent-gated Attendance Policy got a bare
no-source refusal with no "log in" hint, while the same question as a parent returns a full
answer with three citations. One case is an anecdote. This asks the same of the whole gated
corpus, as a guest, and pairs it with public questions that must produce **no** hint - because
D-221's rule is that a gate is scored in both directions or not at all.

**Why this exists alongside `measure_access_probe_rules.py`.** That script sweeps candidate
matching rules offline against a corpus-derived fixture, which is the right instrument for
*choosing* a rule. It cannot tell you what the deployed system does to a real question through
the real edge, and this can - end to end, through CloudFront, against the real corpus and real
Titan embeddings, as a genuinely anonymous caller. Use this for "is it working", that one for
"what should it be".

Read-only. Each question is one real chat turn, so a full run is a few cents; it refuses to
run without `CONFIRM_PAID_RUN=1` for that reason.

    CONFIRM_PAID_RUN=1 uv run python scripts/measure_access_hint_live.py

**Baseline, 2026-08-15 (build `gha-7d1bf6794b09`): recall 1/8, precision 5/5.** Seven of eight
questions a gated document answers produced a bare refusal with no hint; no public question
produced a false one. So the probe is heavily biased toward silence, which is the safe
direction (D-221) and also means it is not doing the job SPEC §18-C3 gives it. AUD-C-20's known
false hint bounds how far recall can be moved, so any tuning has to re-run both columns here.

One incidental finding worth keeping: "What does the tutor handbook require before a session
starts?" is *answered* to a guest, and that is **not** a leak - it cites
`public-student-participation-guide`, a public document, so role filtering held. The answer
opens "According to the tutor handbook", adopting the question's framing while citing
something else. A prose-attribution wart, not an authorization one.
"""

import json
import os
import time
import urllib.error
import urllib.request

BASE = "https://d222glidpp4azv.cloudfront.net"

# Questions a GATED document answers. A guest asking these should be told which role can see
# it - that is what SPEC §18-C3's access hint is for.
GATED = [
    ("parent/attendance-policy", "What is the attendance policy if my child misses a session?"),
    ("parent/attendance-policy", "What happens if my child is marked absent for the week?"),
    ("parent/parent-handbook", "What does the parent handbook say about my responsibilities?"),
    (
        "tutor/instructional-procedures",
        "What instructional procedures should a tutor follow in a session?",
    ),
    ("tutor/student-support-guide", "How should a tutor support a struggling student?"),
    ("tutor/tutor-handbook", "What does the tutor handbook require before a session starts?"),
    ("student/participation", "What does a student need to do to prepare for the weekly pre-exam?"),
    (
        "branch_manager/*",
        "What are a branch manager's responsibilities for staffing a branch?",
    ),
]

# Questions the PUBLIC corpus answers. A hint here is a false positive: it tells a visitor to
# sign in for something they can already read.
PUBLIC = [
    ("public/about", "What is IntelliChoice?"),
    ("public/branch-directory", "What are the Saturday hours?"),
    ("public/about", "Do you offer online tutoring?"),
    ("public/branch-directory", "How do I get in touch with a branch?"),
    ("public/about", "What grade levels do you serve?"),
]


def ask(question: str) -> dict:
    session = json.loads(
        urllib.request.urlopen(
            urllib.request.Request(f"{BASE}/chat/sessions", method="POST", data=b""), timeout=30
        ).read()
    )["chat_session_id"]
    body = json.dumps({"query": question}).encode()
    req = urllib.request.Request(
        f"{BASE}/chat/sessions/{session}/messages",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as response:
        return json.loads(response.read())


def classify(result: dict) -> str:
    hint = result.get("access_hint")
    if hint:
        return f"HINT({hint['required_role']})"
    if result.get("citations"):
        return "ANSWERED"
    if result.get("escalation_recommended"):
        return "REFUSED+ESCALATE"
    if (result.get("scope") or "") == "out_of_scope":
        return "OUT_OF_SCOPE"
    return "OTHER"


def main() -> None:
    print(f"{'class':<8} {'source':<34} outcome")
    tallies: dict[str, dict[str, int]] = {"gated": {}, "public": {}}
    for label, cases in (("gated", GATED), ("public", PUBLIC)):
        for source, question in cases:
            try:
                outcome = classify(ask(question))
            except urllib.error.HTTPError as exc:
                outcome = f"HTTP {exc.code}"
            except Exception as exc:  # noqa: BLE001 - a measurement, not a service
                outcome = f"ERROR {type(exc).__name__}"
            tallies[label][outcome] = tallies[label].get(outcome, 0) + 1
            print(f"{label:<8} {source:<34} {outcome}   | {question[:60]}")
            time.sleep(1)

    hinted = sum(v for k, v in tallies["gated"].items() if k.startswith("HINT"))
    false_hints = sum(v for k, v in tallies["public"].items() if k.startswith("HINT"))
    print()
    print(f"RECALL    gated questions that produced a hint: {hinted}/{len(GATED)}")
    print(f"PRECISION public questions that wrongly hinted: {false_hints}/{len(PUBLIC)}")
    print(f"gated outcomes:  {tallies['gated']}")
    print(f"public outcomes: {tallies['public']}")


if os.environ.get("CONFIRM_PAID_RUN") == "1":
    main()
else:
    print("refusing to spend without CONFIRM_PAID_RUN=1")
