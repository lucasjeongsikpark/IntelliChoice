"""D-401: every alarm routes to exactly one severity channel, and the quiet one is a closed list.

The 08-16 audit filed *"all 26 alarms deliver to one email address, so at 2am the alarm and the
parent's email arrive together at 8am"*. The delay was never the real cost. The real cost is that
**one permanently-firing informational alarm makes every other alarm unreadable**, and the project
is in that state now: the LangSmith quota is exhausted and `langsmith_ingest_failed`'s own
description records that the client *"retries a 403 forever at WARNING"*.

So the fix is two SNS topics, and the risk the fix introduces is the reason this file exists: an
alarm that lands in the quiet channel by accident is *worse* than the single-inbox problem, because
it looks monitored and is not. This test makes the quiet channel a closed list that has to be edited
deliberately, and makes an unrouted alarm fail rather than fall somewhere by default.

Terraform is parsed rather than planned, following `test_deployed_route_admission_parity.py`'s
precedent (D-385): the property is about what the configuration *says*, no AWS credentials are
needed, and it runs in CI where `terraform plan` cannot.
"""

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_OBSERVABILITY = _REPO_ROOT / "terraform" / "modules" / "observability"

# The only alarms that may notify the quiet channel, and why each one qualifies. The admission rule
# is narrow on purpose: an alarm belongs here only if its own description says users are unaffected,
# or if it reports a business floor rather than a fault.
_INFORMATIONAL = {
    # Its own alarm_description: "The AI-observability leg is dark while this is firing; app
    # traffic is unaffected, so nothing else will tell you."
    "langsmith_ingest_failed",
    # Being *above* a capacity floor is the healthy state being reported.
    "capacity_above_floor",
    # A KPI floor going unmet is a product signal; on staging it is the normal overnight state.
    "sessions_completed_floor",
}

_ALARM_BLOCK = re.compile(
    r'resource\s+"aws_cloudwatch_metric_alarm"\s+"(?P<name>\w+)"\s*\{(?P<body>.*?)\n\}',
    re.DOTALL,
)


def _alarms() -> dict[str, str]:
    """Every alarm the observability module declares, name -> body."""
    found: dict[str, str] = {}
    for path in sorted(_OBSERVABILITY.glob("*.tf")):
        for match in _ALARM_BLOCK.finditer(path.read_text()):
            found[match.group("name")] = match.group("body")
    return found


def _topics(body: str) -> set[str]:
    return set(re.findall(r"aws_sns_topic\.(\w+)\.arn", body))


def test_every_alarm_notifies_exactly_one_severity_channel() -> None:
    """No alarm may be unrouted, and none may fan out to both.

    Unrouted is the failure that matters: an alarm with no `alarm_actions` is indistinguishable
    from a working one in the console, and this module has fifteen of them to keep track of. Both
    at once is the other direction - it would double every page and make the split pointless.
    """
    alarms = _alarms()
    assert len(alarms) >= 15, f"parser found only {len(alarms)} alarms; the regex has drifted"

    for name, body in sorted(alarms.items()):
        topics = _topics(body)
        assert topics, f"{name} notifies nothing at all"
        assert topics <= {"alerts", "alerts_info"}, f"{name} notifies an unknown topic: {topics}"
        assert len(topics) == 1, f"{name} notifies both channels: {topics}"


def test_the_quiet_channel_is_exactly_the_reviewed_list() -> None:
    """Both directions, because the useful half is the one that fails when someone adds an alarm.

    A new alarm defaults to the page channel by construction - there is nothing to forget - so this
    catches the opposite mistake: an outage alarm quietly routed to the channel nobody watches.
    Editing `_INFORMATIONAL` is the deliberate act that this test forces.
    """
    routed_quiet = {name for name, body in _alarms().items() if _topics(body) == {"alerts_info"}}
    assert routed_quiet == _INFORMATIONAL, (
        "the informational channel's membership changed without this list being updated: "
        f"added={sorted(routed_quiet - _INFORMATIONAL)} "
        f"removed={sorted(_INFORMATIONAL - routed_quiet)}"
    )


def test_the_five_hundred_and_spend_alarms_are_never_quiet() -> None:
    """The non-vacuity control for the test above, spelled out by name.

    `routed_quiet == _INFORMATIONAL` would still pass if someone moved `target_5xx` into
    `_INFORMATIONAL` along with the alarm - the list and the terraform would agree with each other
    and both be wrong. These four are the ones whose whole purpose is to wake somebody: users are
    getting errors, the database is about to stop accepting writes, the AI features are down, or
    money is leaving.
    """
    alarms = _alarms()
    for name in ("target_5xx", "rds_free_storage", "bedrock_circuit_open", "bedrock_spend_spike"):
        assert name in alarms, f"{name} no longer exists; this control needs rewriting"
        assert _topics(alarms[name]) == {"alerts"}, f"{name} was moved off the page channel"
