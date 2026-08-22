"""RD-01/D-385: every heartbeat alarm's evaluation window must be 2x its job's own cadence,
capped at the one week CloudWatch will evaluate.

**The second half of the RD-01 story, and a different boundary from the first.**
`test_scheduled_job_event_parity.py` guards terraform-pattern <-> Python-emitter agreement - the
defect that kept `JobCompletions` from ever publishing. This file guards a boundary that stayed
invisible while that one was broken: **terraform-alarm <-> terraform-schedule** agreement.

`app_events.tf` gave all four heartbeats one uniform `period = 172800`, whose comment states the
rule it encodes - *"two days, so one missed night is a blip and two is an alarm"*. Three of the
four jobs are daily and that period is exactly 2x their cadence. `memory-consolidate` is
**weekly** (`cron(30 18 ? * SUN *)`), so the same 2-day window means its alarm is OK for about
two days after each Sunday run and back in ALARM for the other five - permanent weekly flapping
to the page mailbox. Nothing caught it because no document and no test connected "weekly job"
(`scheduled-jobs/main.tf`) with "two-day period" (`observability/app_events.tf`), and while the
alarm could never leave ALARM at all the flapping had nowhere to show.

**The cap is not a preference; CloudWatch refuses the un-capped rule.** The first shape written
here gave the weekly job 2 x 604800 = 1,209,600 s, and the apply came back with, verbatim:

    ValidationError: Metrics cannot be checked across more than a week
    (EvaluationPeriods * Period must be <= 604800) for alarms using period >= 3600

That is a ceiling on `EvaluationPeriods * Period` - the *whole window* - so no re-shaping buys a
longer one: 86400 x 14 is the same 1,209,600 s and is refused identically. Two missed weekly runs
are simply not observable by one CloudWatch alarm. So the rule became `min(2 x cadence, 604800)`
(the RD-01 correction, 2026-08-22), and for the weekly job that is `period = 604800`,
`evaluation_periods = 1`.

**What the cap costs, stated plainly.** The weekly job now pages after the *first* missed run
rather than the second - stricter than the rule the daily jobs get. It does not flap: while the
job is healthy every trailing week contains the last Sunday run, so the Sum is 1 and the alarm
stays OK. `memory-consolidate` runs with `retry_attempts = 0`, and for a job that gets no retry a
false page is the cheap error and a silent skipped week is the expensive one, so the cap errs in
the safe direction.

So the invariant asserted here is the rule the comment already stated, applied per job and clamped
to what the API will accept:

    evaluation window (period x evaluation_periods) == min(2 x cadence, 604800)

A future job added to `nightly_job_events` with a cadence its period does not match fails here
rather than shipping another flapping alarm - or another alarm the API rejects at apply time.

Terraform is parsed rather than planned, following `test_scheduled_job_event_parity.py` and
`test_deployed_route_admission_parity.py` (D-385): the property is about what the configuration
*says*, no AWS credentials are needed, and it runs in CI where `terraform plan` cannot. Every
expression shape this file cannot evaluate **fails loudly** - a window it cannot compute is a
window whose parity it cannot assert, and quietly approximating one would restore exactly the
blindness the file exists to remove.
"""

import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_STAGING_TF = _REPO_ROOT / "terraform" / "environments" / "staging" / "main.tf"
_APP_EVENTS_TF = _REPO_ROOT / "terraform" / "modules" / "observability" / "app_events.tf"
_SCHEDULED_JOBS_TF = _REPO_ROOT / "terraform" / "modules" / "scheduled-jobs" / "main.tf"
_SCHEDULED_JOBS_VARIABLES_TF = (
    _REPO_ROOT / "terraform" / "modules" / "scheduled-jobs" / "variables.tf"
)

_DAY_SECONDS = 86400
_WEEK_SECONDS = 7 * _DAY_SECONDS
# The rule `period = 172800`'s own comment encodes: one missed run is a blip, two is an alarm.
_MISSED_RUNS_TOLERATED = 2
# **Do not raise this, and do not try to reshape around it.** CloudWatch rejected the un-capped
# 14-day window for `memory-consolidate` at apply time with, verbatim:
#
#   ValidationError: Metrics cannot be checked across more than a week
#   (EvaluationPeriods * Period must be <= 604800) for alarms using period >= 3600
#
# The ceiling is on the product `EvaluationPeriods * Period`, so `86400 x 14` is the same
# 1,209,600 s and is refused the same way. A weekly job therefore cannot tolerate a missed run:
# it pages after the first. See the module docstring for why that is the safe direction here.
_CLOUDWATCH_MAX_EVALUATION_WINDOW_SECONDS = _WEEK_SECONDS

_HEARTBEAT_JOB_KEYS = re.compile(r"nightly_job_events\s*=\s*\[(?P<items>[^\]]*)\]", re.DOTALL)
_PERIOD_OVERRIDES = re.compile(r"job_heartbeat_period_seconds\s*=\s*\{(?P<body>[^}]*)\}", re.DOTALL)
_ALARM_BLOCK = re.compile(
    r'resource\s+"aws_cloudwatch_metric_alarm"\s+"nightly_job_heartbeat"\s*\{(?P<body>.*?)\n\}',
    re.DOTALL,
)
_JOBS_LOCAL = re.compile(r"^  jobs = \{$(?P<body>.*?)^  \}$", re.DOTALL | re.MULTILINE)
_JOB_ENTRY = re.compile(
    r'^    "?(?P<job>[\w-]+)"?\s*=\s*\{$(?P<body>.*?)^    \}$', re.DOTALL | re.MULTILINE
)
_SCHEDULE_LINE = re.compile(r'^\s*schedule\s*=\s*"(?P<cron>cron\([^"]*\))"\s*$', re.MULTILINE)
_ENABLED_LINE = re.compile(r"^\s*enabled\s*=\s*(?P<enabled>[\w.]+)\s*(?:#.*)?$", re.MULTILINE)
_MAP_NUMBER_ENTRY = re.compile(
    r'^\s*"?(?P<key>[\w-]+)"?\s*=\s*(?P<value>\d+)\s*(?:#.*)?$', re.MULTILINE
)
_LOCALS_BLOCK = re.compile(r"^locals \{$(?P<body>.*?)^\}$", re.DOTALL | re.MULTILINE)
_ATTRIBUTE_LINE = re.compile(r"^\s*{name}\s*=\s*(?P<value>.*?)\s*(?:#.*)?$", re.MULTILINE)

# `cron(<minute> <hour> <day-of-month> <month> <day-of-week> <year>)` - EventBridge's six-field
# form, the only one `scheduled-jobs` writes. Exactly two cadences exist in this repository and
# both are recognised below by their literal shape; anything else is refused rather than guessed.
_CRON_FIELDS = re.compile(r"^cron\((?P<fields>.*)\)$")

# `lookup(var.job_heartbeat_period_seconds, each.key, local.<name>)` - the one non-literal
# `period` expression this test knows how to evaluate.
_PERIOD_LOOKUP = re.compile(
    r"^lookup\(\s*var\.job_heartbeat_period_seconds\s*,\s*each\.key\s*,"
    r"\s*local\.(?P<default_local>\w+)\s*\)$"
)


def _heartbeat_job_keys() -> list[str]:
    """The job keys staging heartbeat-alarms, in declaration order."""
    match = _HEARTBEAT_JOB_KEYS.search(_STAGING_TF.read_text())
    assert match is not None, f"nightly_job_events no longer parses out of {_STAGING_TF}"
    keys = re.findall(r'"([^"]+)"', match.group("items"))
    assert len(keys) >= 4, (
        f"parser found only {keys} heartbeat job keys; the regex or the environment has drifted"
    )
    return keys


def _period_overrides() -> dict[str, int]:
    """Staging's per-job heartbeat period map. Absent (pre-RD-01 shape) reads as empty."""
    match = _PERIOD_OVERRIDES.search(_STAGING_TF.read_text())
    if match is None:
        return {}
    return {
        entry.group("key"): int(entry.group("value"))
        for entry in _MAP_NUMBER_ENTRY.finditer(match.group("body"))
    }


def _module_number_locals() -> dict[str, int]:
    """Plain `name = <integer>` locals declared in `app_events.tf`."""
    numbers: dict[str, int] = {}
    for block in _LOCALS_BLOCK.finditer(_APP_EVENTS_TF.read_text()):
        for entry in _MAP_NUMBER_ENTRY.finditer(block.group("body")):
            numbers[entry.group("key")] = int(entry.group("value"))
    return numbers


def _alarm_body() -> str:
    match = _ALARM_BLOCK.search(_APP_EVENTS_TF.read_text())
    assert match is not None, (
        'the aws_cloudwatch_metric_alarm "nightly_job_heartbeat" resource no longer parses '
        f"out of {_APP_EVENTS_TF}"
    )
    return match.group("body")


def _alarm_attribute(name: str) -> str:
    """The right-hand side of a single-line attribute of the heartbeat alarm."""
    match = re.compile(_ATTRIBUTE_LINE.pattern.format(name=name), re.MULTILINE).search(
        _alarm_body()
    )
    assert match is not None, (
        f"the nightly_job_heartbeat alarm no longer has a single-line `{name}`; this test "
        "cannot evaluate its evaluation window without one"
    )
    return match.group("value")


def _render_period(job_key: str) -> int:
    """Evaluate the alarm's `period` expression for one `each.key`, without a terraform binary.

    Two shapes are understood: a bare integer literal (the uniform pre-RD-01 configuration) and
    the per-job `lookup(...)` that replaced it. Anything else fails loudly - see the module
    docstring, and `_render_pattern` in `test_scheduled_job_event_parity.py` for the same idiom.
    """
    expression = _alarm_attribute("period")
    if expression.isdigit():
        return int(expression)
    lookup = _PERIOD_LOOKUP.match(expression)
    if lookup is None:
        pytest.fail(
            f"unrecognised terraform `period` expression `{expression}` on the "
            "nightly_job_heartbeat alarm; teach this test to evaluate it before changing it"
        )
    overrides = _period_overrides()
    if job_key in overrides:
        return overrides[job_key]
    default_local = lookup.group("default_local")
    locals_ = _module_number_locals()
    assert default_local in locals_, (
        f"the alarm's `period` falls back to `local.{default_local}`, which is not a plain "
        f"integer local in {_APP_EVENTS_TF}; this test cannot evaluate it"
    )
    return locals_[default_local]


def _render_evaluation_periods(job_key: str) -> int:
    """The alarm's `evaluation_periods`. Only a literal is understood today."""
    expression = _alarm_attribute("evaluation_periods")
    if expression.isdigit():
        return int(expression)
    pytest.fail(
        f"unrecognised terraform `evaluation_periods` expression `{expression}` "
        f"(rendering for {job_key}); teach this test to evaluate it before changing it"
    )


def _evaluation_window_seconds(job_key: str) -> int:
    """What CloudWatch actually waits before this job's alarm can breach."""
    return _render_period(job_key) * _render_evaluation_periods(job_key)


def _job_blocks() -> dict[str, str]:
    """Every entry of `scheduled-jobs`'s `locals.jobs`, by job key."""
    jobs_local = _JOBS_LOCAL.search(_SCHEDULED_JOBS_TF.read_text())
    assert jobs_local is not None, f"`locals.jobs` no longer parses out of {_SCHEDULED_JOBS_TF}"
    blocks = {
        entry.group("job"): entry.group("body")
        for entry in _JOB_ENTRY.finditer(jobs_local.group("body"))
    }
    assert blocks, f"no job entries parsed out of `locals.jobs` in {_SCHEDULED_JOBS_TF}"
    return blocks


def _job_schedules() -> dict[str, str]:
    """Job key -> its EventBridge cron expression, verbatim."""
    schedules: dict[str, str] = {}
    for job, body in _job_blocks().items():
        match = _SCHEDULE_LINE.search(body)
        assert match is not None, f"the `{job}` job entry no longer has a single-line `schedule`"
        schedules[job] = match.group("cron")
    return schedules


def _cadence_seconds(job_key: str, cron: str) -> int:
    """How often the schedule fires, in seconds.

    Only the two shapes `scheduled-jobs` has ever used are classified - daily
    (`cron(<m> <h> * * ? *)`) and weekly-on-one-weekday (`cron(<m> <h> ? * SUN *)`). A third
    shape (hourly, twice-weekly, day-of-month) must teach this function before it ships, because
    a cadence guessed wrong here silently licenses the wrong alarm window - the exact defect
    this file exists to catch.
    """
    fields = _CRON_FIELDS.match(cron)
    assert fields is not None, f"{job_key}: `{cron}` is not an EventBridge `cron(...)` expression"
    parts = fields.group("fields").split()
    assert len(parts) == 6, (
        f"{job_key}: `{cron}` does not have EventBridge's six cron fields: {parts}"
    )
    minute, hour, day_of_month, month, day_of_week, year = parts
    # A fixed minute *and* hour is what makes the tail below mean "once a day" rather than
    # "every hour at :00" - `cron(0 * * * ? *)` has the same tail as `cron(0 18 * * ? *)`.
    fires_once_a_day = minute.isdigit() and hour.isdigit()
    if fires_once_a_day and (day_of_month, month, day_of_week, year) == ("*", "*", "?", "*"):
        return _DAY_SECONDS
    if (
        fires_once_a_day
        and (day_of_month, month, year) == ("?", "*", "*")
        and re.fullmatch(r"(MON|TUE|WED|THU|FRI|SAT|SUN)", day_of_week)
    ):
        return _WEEK_SECONDS
    pytest.fail(
        f"{job_key}: cannot classify the cadence of `{cron}`. This test knows only daily "
        "(`* * ? *`) and weekly-on-one-weekday (`? * <DAY> *`) tails; teach it the new shape "
        "before scheduling a job on it, or its heartbeat window cannot be checked"
    )


def _required_window_seconds(job_key: str, cron: str) -> int:
    """2x the cadence, clamped to the longest window CloudWatch will evaluate (RD-01 correction)."""
    return min(
        _MISSED_RUNS_TOLERATED * _cadence_seconds(job_key, cron),
        _CLOUDWATCH_MAX_EVALUATION_WINDOW_SECONDS,
    )


def test_every_heartbeat_window_is_the_capped_two_run_rule() -> None:
    """RD-01's residual. One assertion per job, so the failure names the job that flaps."""
    schedules = _job_schedules()

    for job_key in _heartbeat_job_keys():
        assert job_key in schedules, (
            f"{job_key} is heartbeat-alarmed but has no entry in `locals.jobs` - the alarm "
            "carries `job` as a dimension, so this one can never receive a datapoint"
        )
        cron = schedules[job_key]
        cadence = _cadence_seconds(job_key, cron)
        required = _required_window_seconds(job_key, cron)
        actual = _evaluation_window_seconds(job_key)
        capped = _MISSED_RUNS_TOLERATED * cadence > required
        rule = (
            "2x that cadence exceeds the 604800 s CloudWatch will evaluate "
            "(`EvaluationPeriods * Period must be <= 604800`), so the window is capped at one "
            "week and this job pages after its first missed run"
            if capped
            else "one missed run is a blip and two is an alarm"
        )
        assert actual == required, (
            f"{job_key}: schedule `{cron}` fires every {cadence // _DAY_SECONDS} day(s), so its "
            f"heartbeat needs a {required // _DAY_SECONDS}-day evaluation window - {rule}. The "
            f"alarm renders {actual // _DAY_SECONDS} day(s) (period {_render_period(job_key)} x "
            f"{_render_evaluation_periods(job_key)}). Too short and the alarm re-enters ALARM "
            "between every run; too long and either a missed run goes unreported or the API "
            "rejects the alarm at apply time"
        )


def test_the_alarm_description_states_each_job_own_window() -> None:
    """The operator-facing half: a description that lies is worse than no description.

    The pre-RD-01 text hard-coded *"the ${each.key} nightly job has not reported a completion in
    48h"* for all four jobs, which would have read as a 48-hour outage on a job that is not even
    due for another five days. Whoever is paged at 02:00 reads this string, not the terraform.
    """
    description = _alarm_body()
    assert "48h" not in description, (
        "the heartbeat `alarm_description` still hard-codes `48h`; it is rendered for every job "
        "including the weekly one, whose window is 7 days"
    )
    assert "nightly job" not in description, (
        "the heartbeat `alarm_description` still calls every job `nightly`; `memory-consolidate` "
        "is weekly, and the misnomer is what hid this defect"
    )

    assert "${each.key}" in description, (
        "the heartbeat `alarm_description` no longer names the job it fired for"
    )

    for job_key in _heartbeat_job_keys():
        window_days = _evaluation_window_seconds(job_key) // _DAY_SECONDS
        rendered = _rendered_description(job_key)
        assert f"{window_days} days" in rendered, (
            f"{job_key}: its alarm description does not state its own "
            f"{window_days}-day window: {rendered!r}"
        )


def _rendered_description(job_key: str) -> str:
    """Evaluate the `alarm_description` for one `each.key`, interpolations included.

    Exactly the interpolations this description has ever used are understood; anything else
    fails loudly, for the same reason `_render_period` does.
    """
    match = re.search(
        r"alarm_description = join\(\" \", \[(?P<items>.*?)\n  \]\)", _alarm_body(), re.DOTALL
    )
    assert match is not None, (
        'the heartbeat `alarm_description` is no longer a `join(" ", [...])` of string '
        "literals; teach this test to render its new shape"
    )
    text = " ".join(re.findall(r'^\s*"(?P<line>.*)",$', match.group("items"), re.MULTILINE))

    def _interpolate(interpolation: re.Match[str]) -> str:
        expression = interpolation.group("expr").strip()
        if expression == "each.key":
            return job_key
        divided = re.fullmatch(r"(?P<inner>.*?)\s*/\s*(?P<divisor>\d+)", expression)
        if divided is not None and _PERIOD_LOOKUP.match(divided.group("inner").strip()):
            return str(_render_period(job_key) // int(divided.group("divisor")))
        pytest.fail(
            f"unrecognised terraform interpolation `${{{expression}}}` in the heartbeat "
            "alarm_description; teach this test to evaluate it before changing it"
        )

    return re.sub(r"\$\{(?P<expr>[^}]*)\}", _interpolate, text)


def _job_enabled_by_default(job_key: str) -> bool:
    """Whether `locals.jobs[job_key].enabled` is on with the module's own variable defaults.

    `enabled` is not always a literal - D-406 drives `youtube-sync` from
    `var.youtube_sync_enabled` so that turning the sync on and turning NAT on stay one edit.
    A `var.<name>` reference is resolved to that variable's declared default; a `.tfvars`
    override is deliberately out of reach here (this repository's tfvars are never read by
    tests), which is sound for what this asserts: the checked-in posture, and the fact that
    changing it is a visible diff that lands on this test.
    """
    match = _ENABLED_LINE.search(_job_blocks()[job_key])
    assert match is not None, f"the `{job_key}` job entry no longer has a single-line `enabled`"
    expression = match.group("enabled")
    if expression in ("true", "false"):
        return expression == "true"
    variable = re.fullmatch(r"var\.(?P<name>\w+)", expression)
    if variable is None:
        pytest.fail(
            f"unrecognised `enabled` expression `{expression}` on the {job_key} job; teach "
            "this test to evaluate it before changing it"
        )
    default = re.search(
        rf'variable "{variable.group("name")}" \{{(?P<body>[^}}]*)\}}',
        _SCHEDULED_JOBS_VARIABLES_TF.read_text(),
        re.DOTALL,
    )
    assert default is not None, (
        f"`var.{variable.group('name')}` is not declared in {_SCHEDULED_JOBS_VARIABLES_TF}"
    )
    literal = re.search(
        r"^\s*default\s*=\s*(?P<value>true|false)\s*$", default.group("body"), re.MULTILINE
    )
    assert literal is not None, (
        f"`var.{variable.group('name')}` has no boolean `default`; this test cannot evaluate it"
    )
    return literal.group("value") == "true"


def test_scheduled_jobs_without_a_heartbeat_are_skipped_deliberately() -> None:
    """The explicit skip, so "no heartbeat" stays a decision rather than an oversight.

    `youtube-sync` has a schedule and no heartbeat alarm, and that is correct: it is
    `enabled = false`, so a heartbeat on it would breach forever and teach everyone to ignore
    the page channel. The test above iterates the *heartbeat* list rather than the schedule
    list for exactly this reason; this test pins the one job that difference covers, so that
    a newly-scheduled job silently missing a heartbeat is visible here as a changed skip set.
    """
    unheartbeated = set(_job_schedules()) - set(_heartbeat_job_keys())
    assert unheartbeated == {"youtube-sync"}, (
        f"the set of scheduled jobs with no heartbeat alarm changed to {sorted(unheartbeated)}. "
        "If a job was added, decide whether it needs a heartbeat (and a window matching its "
        "cadence) rather than letting it inherit this skip"
    )
    assert not _job_enabled_by_default("youtube-sync"), (
        "youtube-sync is now enabled by default, so its exemption from the heartbeat list no "
        "longer holds: an enabled job with no dead-man's switch is the RD-01 blind spot again"
    )


def test_the_cadence_rule_rejects_a_uniform_window() -> None:
    """The non-vacuity control (D-221), scoring the negative direction too.

    A rule that accepted any window would pass the test above while `memory-consolidate` flapped
    every week - which is the *actual* defect's shape, not a hypothetical. So: the uniform
    two-day window the configuration shipped with must be rejected for a weekly job, and the
    weekly window must be rejected for a daily one.

    The cap is scored in both directions too. It must bite on the weekly job (2 x 604800 is the
    window CloudWatch refused) and it must *not* silently widen a daily job's window to a week,
    which is how a badly-written clamp goes vacuous.
    """
    assert _required_window_seconds("weekly-job", "cron(30 18 ? * SUN *)") == 7 * _DAY_SECONDS
    assert _required_window_seconds("daily-job", "cron(0 18 * * ? *)") == 2 * _DAY_SECONDS

    # The shipped uniform period, scored against both cadences.
    assert 172800 != _required_window_seconds("weekly-job", "cron(30 18 ? * SUN *)")
    assert 172800 == _required_window_seconds("daily-job", "cron(0 18 * * ? *)")

    # The window the API rejected must never be what this rule asks for again, and the clamp
    # must be the thing doing it - an uncapped 2x weekly is 1,209,600 s.
    assert _MISSED_RUNS_TOLERATED * _WEEK_SECONDS > _CLOUDWATCH_MAX_EVALUATION_WINDOW_SECONDS
    for job_key, cron in (
        ("weekly-job", "cron(30 18 ? * SUN *)"),
        ("daily-job", "cron(0 18 * * ? *)"),
    ):
        assert (
            _required_window_seconds(job_key, cron) <= _CLOUDWATCH_MAX_EVALUATION_WINDOW_SECONDS
        ), f"{job_key}: the rule asks for a window the CloudWatch API rejects at apply time"

    # Cadence shapes the classifier does not know must fail rather than be approximated. An
    # hourly cron carries the *same* six-field tail as a daily one and differs only in its hour
    # field, so a classifier reading the tail alone would call it daily and license a window 48x
    # too wide.
    for unknown in ("cron(0 * * * ? *)", "cron(0 18 1 * ? *)", "cron(0 18 ? * MON-FRI *)"):
        with pytest.raises(pytest.fail.Exception, match="cannot classify the cadence"):
            _cadence_seconds("unknown-cadence-job", unknown)
