"""Per-event delivery accounting for E1.2's two SSE tiers (MEASUREMENT_PLAN Theme 1).

**Why a ledger and not a counter.** The evidence this repository already has for the
cross-replica relay is `load-tests/sse_load.py`'s "connected / received >= 1 event" and the
10-round probes behind D-349. Both answer *did anything arrive*. Neither can answer *did every
event arrive*, which is the actual claim a fan-out relay makes, and the difference is where the
D-395 defect lived: a five-event burst delivered one event and lost four, and a first-event
counter would have called that stream a success.

So each stream keeps an ordered list of what it *asked for* and what *arrived*, and the summary
is computed from the pair. Rates carry their denominator by construction.

### The three accounting rules, and the honest limits of each

1. **The initial snapshot is not a delivery.** `routers/stream.py` yields the current checkpoint
   snapshot on every (re)connect before it ever reads the queue. Counting it would credit a
   delivery to a stream whose relay is completely dead - the exact false pass this instrument
   exists to prevent - so it is counted separately as `initial_snapshots` and never as delivered.

2. **Delivery is credited ordinally, by the driver, one action at a time.** The driver issues
   action k and waits for the next frame before issuing k+1, so at most one event is ever in
   flight per stream and the frame-to-action mapping is unambiguous *by construction* rather
   than by inference. A frame that arrives with no action outstanding cannot be matched to
   anything and is recorded as `unmatched_frames`, which is what a duplicate (a relay echo that
   escaped the origin guard) looks like from here.

3. **Ordering is only decidable where content is.** Measured on the local rig 2026-08-29:
   during `pre_exam`, `select_topic` and all ten answer snapshots serialize to the *same* JSON -
   phase, items, and every other snapshot field are unchanged by an answer whose correctness is
   masked (D-064). So the frames genuinely carry no information that could reveal a reordering.
   Rather than report a meaningless `out_of_order: 0`, the summary reports how many events were
   *decidable* (stream-unique content hash) alongside how many were out of order among them. A
   reader can then see that the ordering claim rests on n decidable events, not on all of them.
   This is not a gap in the product: an event is a **complete** snapshot the client swaps in
   whole (`services/session_events.py`), so a late frame overwrites with equally-current state
   and ordering is not a correctness property here. It is a gap in what the instrument can see,
   and it belongs in the instrument's own output.

Pure: no I/O, no network, no clock of its own. Every timestamp is passed in.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

# The `SessionSnapshotEvent` field set (apps/learning-api/src/learning_api/routers/sessions.py),
# minus the constant `event` discriminator. Hashing this rather than the raw frame lets an
# action's HTTP *response* and the SSE frame it published be compared directly: the publish path
# is `SessionSnapshotEvent.model_validate(response.model_dump())`, so the two are the same
# object seen through two serializations.
SNAPSHOT_FIELDS = (
    "learning_session_id",
    "phase",
    "message",
    "is_correct",
    "items",
    "learning_gain",
    "pending_interrupt",
    "intervention",
    "assistance_question",
    "study_progress",
    "attendance_resolution",
    "stage_narrative",
    "stage_narrative_evidence",
    "stage_narrative_stage",
)


def content_hash(payload: dict[str, Any] | None) -> str:
    """A stable digest of the snapshot-shaped subset of a dict.

    Absent and explicitly-null fields hash identically on purpose: an action response carries
    only the fields its own response model declares, while the published frame carries the full
    superset with nulls, and the two must agree for the comparison to mean anything.
    """
    if payload is None:
        return ""
    subset = {k: payload.get(k) for k in SNAPSHOT_FIELDS}
    return hashlib.sha256(
        json.dumps(subset, sort_keys=True, default=str, separators=(",", ":")).encode()
    ).hexdigest()


def percentile(values: list[float], q: float) -> float | None:
    """Nearest-rank percentile. Deliberately not `statistics.quantiles`: at the small per-stream
    n this runs on, interpolation invents a latency no request ever had."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, min(len(ordered), int(round(q * len(ordered) + 0.5))))
    return ordered[rank - 1]


@dataclass
class ExpectedEvent:
    index: int
    action: str
    issued_at: float
    content_hash: str
    delivered_at: float | None = None
    delivered_hash: str | None = None
    # Set instead of `delivered_at` when the event was not pushed to a live stream but the
    # state it carried was recovered by the reconnect's initial snapshot - see
    # `StreamLedger.record_recovery`.
    recovered_at: float | None = None


def delivery_latencies_ms(events: list[ExpectedEvent]) -> list[float]:
    """Push latency for every credited delivery, in ms.

    A function rather than a comprehension so the `delivered_at is not None` narrowing happens
    once, in one place, instead of being re-asserted at each of the three call sites.
    """
    return [(e.delivered_at - e.issued_at) * 1000.0 for e in events if e.delivered_at is not None]


@dataclass
class StreamLedger:
    """One SSE stream's account. `arm` distinguishes the cross-process case (the POST went to
    the *other* process, so delivery requires the relay) from the same-process control."""

    stream_id: str
    arm: str
    expected: list[ExpectedEvent] = field(default_factory=list)
    unmatched_frames: list[dict[str, Any]] = field(default_factory=list)
    initial_snapshots: int = 0
    # The connect snapshot's content. Not a delivery (rule 1), but it is the state the first
    # pushed event is a *transition away from*, which is what makes that first event's ordering
    # decidable at all.
    initial_hash: str | None = None
    keepalives: int = 0
    reconnects: int = 0
    stream_errors: list[str] = field(default_factory=list)

    def record_expected(self, action: str, issued_at: float, payload: dict[str, Any]) -> int:
        idx = len(self.expected)
        self.expected.append(
            ExpectedEvent(
                index=idx, action=action, issued_at=issued_at, content_hash=content_hash(payload)
            )
        )
        return idx

    def record_delivery(self, index: int, received_at: float, frame: dict[str, Any]) -> None:
        ev = self.expected[index]
        if ev.delivered_at is not None:
            # Never overwrite a credited delivery: a second frame for an already-satisfied
            # action is a duplicate, and silently replacing the first would hide it.
            self.unmatched_frames.append(
                {"t": received_at, "hash": content_hash(frame), "reason": "duplicate_for_index"}
            )
            return
        ev.delivered_at = received_at
        ev.delivered_hash = content_hash(frame)

    def record_recovery(self, index: int, received_at: float, frame: dict[str, Any]) -> None:
        """Credit a *state recovery*, not a delivery.

        Through CloudFront a stream can be cut at the 60 s read timeout mid-action. The event
        published during that gap reached nobody - the relay is fire-and-forget by design
        (`session_event_relay.py`, "What is deliberately accepted") - but the reconnect re-reads
        the checkpoint, so the client ends up with the right state anyway.

        Counting that as a delivery would flatter the push channel; counting it as a loss would
        misrepresent what the student experienced. It is a third outcome and gets a third
        counter, so `delivery_rate` stays a statement about the *push* path and
        `state_convergence_rate` is the one about what the client ended up holding. Only
        credited when the recovered snapshot actually matches the expected content - a
        reconnect that restored some *other* state is a loss.
        """
        ev = self.expected[index]
        if ev.delivered_at is not None or ev.recovered_at is not None:
            self.unmatched_frames.append(
                {"t": received_at, "hash": content_hash(frame), "reason": "duplicate_for_index"}
            )
            return
        if content_hash(frame) != ev.content_hash:
            return
        ev.recovered_at = received_at

    def record_unmatched(self, received_at: float, frame: dict[str, Any], reason: str) -> None:
        self.unmatched_frames.append(
            {"t": received_at, "hash": content_hash(frame), "reason": reason}
        )

    def summary(self) -> dict[str, Any]:
        delivered = [e for e in self.expected if e.delivered_at is not None]
        recovered = [e for e in self.expected if e.recovered_at is not None]
        lost = [e for e in self.expected if e.delivered_at is None and e.recovered_at is None]
        latencies = delivery_latencies_ms(delivered)

        # Ordering, only where content can decide it - see rule 3 in the module docstring.
        #
        # **Decidability lives in the transitions, not in the events.** Requiring an event's
        # content to be unique across the whole stream reports zero decidable events on this
        # flow, because a pre-exam answer changes no snapshot field and a post-finalize resume
        # re-serves the study snapshot verbatim - so the events fall into two large identical
        # groups. But the *boundary* between those groups is sharp: the frame credited to the
        # first `study` action must carry `study`, and if a stale `pre_exam` frame were served
        # there instead, that is exactly a reordering and it is visible.
        #
        # So a transition is any delivered event whose expected content differs from the content
        # immediately before it (the previous expected event, or the connect snapshot for the
        # first one). At a transition the credited frame either carries the new content
        # (agreement) or carries the previous content (`out_of_order` - a stale frame served
        # where the state had already moved).
        previous_hashes: dict[int, str | None] = {}
        prior: str | None = self.initial_hash
        for e in self.expected:
            previous_hashes[e.index] = prior
            prior = e.content_hash
        transitions = [
            e
            for e in delivered
            if previous_hashes[e.index] is not None and previous_hashes[e.index] != e.content_hash
        ]
        out_of_order = [
            e.index for e in transitions if e.delivered_hash == previous_hashes[e.index]
        ]
        decidable = transitions

        return {
            "stream_id": self.stream_id,
            "arm": self.arm,
            "expected": len(self.expected),
            "delivered": len(delivered),
            "recovered_on_reconnect": len(recovered),
            "lost": len(lost),
            "lost_indices": [e.index for e in lost],
            "lost_actions": sorted({e.action for e in lost}),
            "unmatched_frames": len(self.unmatched_frames),
            "initial_snapshots": self.initial_snapshots,
            "keepalives": self.keepalives,
            "reconnects": self.reconnects,
            "stream_errors": self.stream_errors,
            "content_agreements": sum(1 for e in delivered if e.delivered_hash == e.content_hash),
            "content_disagreements": sum(
                1 for e in delivered if e.delivered_hash != e.content_hash
            ),
            "ordering_decidable_transitions": len(decidable),
            "ordering_transition_agreements": sum(
                1 for e in decidable if e.delivered_hash == e.content_hash
            ),
            "out_of_order": len(out_of_order),
            "out_of_order_indices": out_of_order,
            "latency_ms": {
                "n": len(latencies),
                "p50": percentile(latencies, 0.50),
                "p95": percentile(latencies, 0.95),
                "p99": percentile(latencies, 0.99),
                "max": max(latencies) if latencies else None,
            },
        }


def aggregate(ledgers: list[StreamLedger]) -> dict[str, Any]:
    """Totals, plus the same totals split by arm - the split is the point on the local rig,
    where a same-process control arm isolates a relay failure from a bus failure."""
    per_stream = [led.summary() for led in ledgers]
    all_latencies = delivery_latencies_ms([e for led in ledgers for e in led.expected])

    def totals(rows: list[dict[str, Any]], latencies: list[float]) -> dict[str, Any]:
        expected = sum(r["expected"] for r in rows)
        delivered = sum(r["delivered"] for r in rows)
        recovered = sum(r.get("recovered_on_reconnect", 0) for r in rows)
        return {
            "streams": len(rows),
            "expected": expected,
            "delivered": delivered,
            "recovered_on_reconnect": recovered,
            "lost": sum(r["lost"] for r in rows),
            # Denominator carried with the rate, always (MEASUREMENT_PLAN evidence rules).
            # `delivery_rate` is about the push path alone; `state_convergence_rate` adds the
            # events whose state the checkpoint restored on reconnect. Two different claims,
            # kept apart on purpose.
            "delivery_rate": (delivered / expected) if expected else None,
            "delivery_fraction": f"{delivered}/{expected}",
            "state_convergence_rate": ((delivered + recovered) / expected) if expected else None,
            "state_convergence_fraction": f"{delivered + recovered}/{expected}",
            "unmatched_frames": sum(r["unmatched_frames"] for r in rows),
            "initial_snapshots": sum(r["initial_snapshots"] for r in rows),
            "keepalives": sum(r["keepalives"] for r in rows),
            "reconnects": sum(r["reconnects"] for r in rows),
            "content_agreements": sum(r["content_agreements"] for r in rows),
            "content_disagreements": sum(r["content_disagreements"] for r in rows),
            "ordering_decidable_transitions": sum(
                r["ordering_decidable_transitions"] for r in rows
            ),
            "ordering_transition_agreements": sum(
                r["ordering_transition_agreements"] for r in rows
            ),
            "out_of_order": sum(r["out_of_order"] for r in rows),
            "streams_with_loss": sum(1 for r in rows if r["lost"]),
            "latency_ms": {
                "n": len(latencies),
                "p50": percentile(latencies, 0.50),
                "p95": percentile(latencies, 0.95),
                "p99": percentile(latencies, 0.99),
                "max": max(latencies) if latencies else None,
            },
        }

    by_arm: dict[str, Any] = {}
    for arm in sorted({r["arm"] for r in per_stream}):
        rows = [r for r in per_stream if r["arm"] == arm]
        lat = delivery_latencies_ms([e for led in ledgers if led.arm == arm for e in led.expected])
        by_arm[arm] = totals(rows, lat)

    return {
        "total": totals(per_stream, all_latencies),
        "by_arm": by_arm,
        "per_stream": per_stream,
    }
