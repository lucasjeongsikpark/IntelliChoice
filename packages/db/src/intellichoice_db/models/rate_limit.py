"""Cross-task rate-limit counters for SPEC §5.24.2's caller caps (AUD-C-27).

The escalation cap was a per-process dict, and a process is one ECS task. Uvicorn runs a
single worker, Terraform sets `autoscaling_min_capacity` 1-2 with `max_capacity` 3, and no
ALB target-group stickiness pins a caller to a task - so one caller's requests spread and
each task enforced its own private copy of "5 per hour". Measured on the deployed system
before the fix: **8 escalation drafts accepted from one IP against a configured 5**.

Same defect class and same remedy as `cost_reservations` (AUD-X-08): a limit enforced from
per-caller state that other callers cannot see is not a limit. The difference is only which
state was invisible - there an uncommitted row, here another task's memory.

**No PII, and that is not incidental here.** A rate-limit key is a caller external id or,
for an anonymous caller, a client IP - and an IP is identifying. Before this table no client
IP was persisted anywhere in Postgres, so the column stores an HMAC of the key
(`intellichoice_shared.rate_limit.hash_caller_key`) and never the key. `test_schema_purity`
enforces the shape of that promise: `ip`, `ip_address` and `client_ip` are on its denylist
because this is the change that would otherwise have introduced the first one.

**Growth is bounded by attempts, not by callers over time**, so no retention job is wired:
`try_consume` prunes this key's own expired rows inside the same transaction it already
holds a lock on, and the residue is rows for keys that never come back - a handful per day
at escalation volume (the cap itself is 5/hour and escalation is a deliberate button
press). If that ever stops being true, `learning_api.services.retention_purge_cli` is where
it goes.
"""

from datetime import datetime

from sqlalchemy import DateTime, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from intellichoice_db.models.base import Base, new_uuid

# Limiter surfaces. Strings rather than a Postgres enum, matching `cost_reservations.scope`
# - adding a surface should be a code change, not a migration.
SCOPE_ADMIN_ESCALATION = "admin_escalation"
# D-345: every chat turn, not just the escalation button. Keyed the same way (external id
# when signed in, client IP when anonymous, HMAC'd either way), so a branch's shared egress
# IP is one key for its anonymous visitors and a distinct key per signed-in one.
SCOPE_CHAT_MESSAGE = "chat_message"


class RateLimitEvent(Base):
    __tablename__ = "rate_limit_events"
    __table_args__ = (
        # The only query shape: (scope, caller, created_at >= window start).
        Index(
            "ix_rate_limit_events_scope_caller_created",
            "scope",
            "caller_key_hash",
            "created_at",
        ),
    )

    event_id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    scope: Mapped[str] = mapped_column(String, nullable=False)
    # HMAC of the caller key, never the key. See the module docstring.
    caller_key_hash: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
