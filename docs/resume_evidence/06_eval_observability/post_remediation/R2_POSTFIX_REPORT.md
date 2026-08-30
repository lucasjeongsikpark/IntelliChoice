# R2 — SILENT-500S + COLLECTOR-STATS-UNSCRAPED: fixes and post-fix verification

**Remediation task R2** of the post-measurement program (user-commissioned 2026-08-29), against
two observability defects: `SILENT-500S` (PROJECT_STATE §4.1, evidence D-455) and
`COLLECTOR-STATS-UNSCRAPED` (E6.2's low-severity finding, the AUD-F-12 blind-spot class).
Reproduce → smallest fix → permanent regression tests → targeted staging apply → read-back.

**Nothing in this directory replaces an E6.x artifact.** `git status docs/resume_evidence/`
reports exactly one untracked path for this task — `06_eval_observability/post_remediation/` —
and no modification to `E6_1_REPORT.md`, `E6_2_REPORT.md`, `trace_coverage_results.json`,
`trace_coverage_summary.csv`, `pii_probe_results.json` or `pii_probe_metrics.csv`.

**No paid model call was made anywhere in this task.** Total spend: the CloudWatch custom
metrics and alarms created below (see §6).

**All timestamps in this document are UTC and are labelled `Z`.** The AWS CLI on this machine
renders `Timestamp` with a `-05:00` offset, so every datapoint below was converted explicitly
before being written down; the raw local-time strings are not reproduced anywhere in this file.

---

## 1. What was wrong, in one paragraph each

**SILENT-500S.** An exception that escapes a route handler emits **no JSON `level=ERROR` line
at all**. D-393 had already fixed the half of this that looked like the whole of it — an
unhandled 500 now produces an access line, a `trace_id` and an `http_requests_total{status="500"}`
increment — and the access line is `logger.info`. So the only structured record of the worst
class of failure this system has read `"level": "INFO"`: invisible to every
`{ $.level = "ERROR" }` metric filter and log alarm, and invisible to the D-454 log-sweep
method, which reads ERROR lines. Worse than the severity: `status_code: 500` says a request
failed and cannot say **what** failed. The exception type and traceback existed only in
uvicorn's plain-text ASGI traceback — prose, in the same log group, arriving as one CloudWatch
event per line because the awslogs driver splits on newlines. Staging emitted **114 traceback
lines** during the 2026-08-29 RDS secret-rotation incident (D-455) while every monitor read
quiet.

**COLLECTOR-STATS-UNSCRAPED.** The ADOT sidecar has always computed its own export counters —
its startup line reads `Serving metrics {"address": "localhost:8888", "metrics level":
"Normal"}` — and the Prometheus receiver's scrape config named the **app port only**. So
`otelcol_exporter_sent_spans` and `otelcol_exporter_send_failed_spans` were computed every
second and read by nothing: **no export success or failure rate existed anywhere in AWS.** That
is AUD-F-12's exact shape. The collector is `essential: false` on purpose (a collector that
dies must not take a healthy API down), which makes its designed failure mode — dying, or
failing every export — silent by construction unless something watches. E6.2 proved the reader
and found zero failures in both windows; it could not close the detection gap, because the gap
is that nobody watches between measurements.

---

## 2. SILENT-500S — before → after

### 2a. Local (app layer) — reproduced, then fixed

**Environment:** local, working tree at `land/remediation-r1` + this task's uncommitted edits.
Python 3.12, `uv run pytest`.

The reproduction is `packages/observability/tests/test_unhandled_exception_logging.py`, written
against the unfixed middleware. **Before** (raw: `raw/R2_prefix_failing_tests.txt`):

```
E       AssertionError: no level=ERROR line was emitted; got ['INFO']
E       assert []
packages/observability/tests/test_unhandled_exception_logging.py:97: AssertionError
...
4 failed, 1 passed in 0.30s
```

The one test that passed pre-fix is the both-apps-wiring assertion, which was already true.
The four that failed are the four properties the defect denied: an ERROR line exists, it
carries the failed request's `trace_id`, its traceback goes through `redact_free_text`, and it
carries no student-identifying key.

**After:**

```
5 passed in 0.25s
```

**The line that did not exist before**, from a real request through the shipped middleware,
formatter and PII filter (`{learning_session_id}` route, `RuntimeError` in the handler):

```json
{"event": "unhandled_exception", "level": "ERROR", "timestamp": "...Z",
 "logger": "intellichoice.errors", "method": "GET",
 "path": "/learning/sessions/{learning_session_id}/answers", "status_code": 500,
 "exception_type": "RuntimeError", "learning_session_id": "s1",
 "exc_info": "Traceback (most recent call last):\n ..."}
```

`level=ERROR`, so an ERROR filter can see it. `exception_type`, so an operator learns what
failed without opening the prose. `exc_info`, redacted by `JsonLogFormatter` per D-394 —
`exc_info` is a standard `LogRecord` attribute and `PiiDenylistFilter` never inspects it, so
the formatter's `redact_free_text` is the only gate and it is applied. `path` is the route
template and `learning_session_id` comes from the D-288 allowlist, both by construction: the
error line calls the **same** `_route_and_session_ids` helper the access line does.

**The fix, and why it is where it is.** `request_logging.install_request_logging_middleware`
already has the `except Exception` block that catches this exact class (D-393) and is already
called by both apps. Adding the ERROR line there means:

- **one catch, one wiring point** — an app cannot be wired for the access line and miss the
  error line, and there is no second `install_*` call for the next app to forget;
- **the same route discipline**, shared rather than re-implemented correctly a second time;
- **no behaviour change** — `app.add_exception_handler(Exception, ...)` was rejected because
  Starlette hands that handler to `ServerErrorMiddleware`, which then builds the 500 response
  *from it*, so registering one to get a log line would quietly replace the error response both
  apps return today.

The access line is unchanged and still `INFO`, so every existing `http_request` query returns
the same rows. `CancelledError` still produces neither line — it derives from `BaseException`
and `except Exception` lets it past, which D-393's own regression test
(`test_a_cancelled_request_is_not_logged_as_a_server_error`) now guards for both lines.

### 2b. Staging (deployed) — the half that needed no deploy

> **The app-side fix is local-verified and is NOT in staging.** The deployed image is
> `gha-5fa15d491057` on both services and the deploy trigger is MANUAL (D-417 §C9). **The
> `unhandled_exception` line reaches staging with the next deploy, not with this task.** That is
> why the second layer below exists: it makes the D-455 class alertable on the image staging is
> running right now, and it keeps working afterwards, because uvicorn writes its own plain-text
> traceback whether or not the app also logged one.

A CloudWatch **metric filter** on the plain-text traceback, plus an alarm, per log group.
Deployed read-back:

```
intellichoice-staging-learning-api-unhandled-tracebacks
  logGroup=/ecs/intellichoice-staging-learning-api
  pattern='"Traceback (most recent call last):" -exc_info'
  metric=IntelliChoice/intellichoice-staging/learning-api/UnhandledTracebacks value=1 default=0.0

intellichoice-staging-chat-api-unhandled-tracebacks
  logGroup=/ecs/intellichoice-staging-chat-api
  pattern='"Traceback (most recent call last):" -exc_info'
  metric=IntelliChoice/intellichoice-staging/chat-api/UnhandledTracebacks value=1 default=0.0
```

**`-exc_info` is the design of the pattern, not a detail.** Two other line shapes in these
groups contain the same phrase and must not be counted: the new `unhandled_exception` JSON
line, whose redacted `exc_info` embeds the formatted traceback (counting it would double every
exception after the next deploy), and `background_*_failed` lines, whose `logger.exception`
does the same and which already have their own filter and alarm. No plain-text traceback line
contains the token `exc_info`; every JSON line carrying a traceback does.

**Validated with `aws logs test-metric-filter` against real captured event text**, not reasoned
about (raw: `raw/R2_test_metric_filter.json`). Seven sample events — three real plain-text
traceback shapes read out of the D-455 incident window, a real `unhandled_exception` line
generated by the fixed code, a `background_*_failed` line, an exception message line, and a
healthy `http_request` line. Without the exclusion: **5 of 7 matched**. With it: **exactly the
3 plain-text lines**.

```
matches: 3
  1 Traceback (most recent call last):
  2   + Exception Group Traceback (most recent call last):
  3     | Traceback (most recent call last):
```

**Stated rather than smoothed over: this counts traceback *lines*, not exceptions.** One chained
or grouped exception writes up to three matching lines. It is a presence signal with the
threshold at zero, not a rate — which is also how D-455's own "114 traceback lines" is phrased.

**End-to-end proof against the deployed filter** (not just the pattern). Three synthetic events
written to `/ecs/intellichoice-staging-learning-api`, log stream
`r2-verification/synthetic-traceback`, at **2026-08-30T04:05:50Z**: one plain-text traceback
line and two JSON lines carrying `exc_info` (one `unhandled_exception`, one
`background_synthetic_failed`). `UnhandledTracebacks`, 60-second periods, UTC:

```
03:54:00Z=0 | 03:55:00Z=0 | 03:56:00Z=0 | 03:57:00Z=0 | 03:58:00Z=0 | 03:59:00Z=0
04:00:00Z=0 | 04:01:00Z=0 | 04:02:00Z=0 | 04:03:00Z=0 | 04:04:00Z=0 | 04:05:00Z=1
```

**One** datapoint for three events: the plain-text line counted, both JSON lines did not. The
alarm followed at **2026-08-30T04:07:05Z** —

```
state  : ALARM as of 2026-08-30T04:07:05Z UTC
reason : Threshold Crossed: 1 datapoint [1.0 ...] was greater than the threshold (0.0).
```

**The alarm's actions were disabled for the duration of this test and restored afterwards**
(§5), so no notification was sent to the alert inbox. The continuous zeros before 04:05 are the
filter's `default_value = 0` doing its job: a quiet window plots as a real zero rather than as a
gap indistinguishable from "nothing is collected".

**Alarm configuration** (both services identical):

| field | value | why |
|---|---|---|
| threshold | `> 0` over `900s`, `evaluation_periods = 1` | An unhandled exception is an event, not a rate — each one is a 500 served on a request the code did not expect to fail. D-455's shape (a credential that stopped working) produces one per request from the first second, so waiting for a second datapoint buys nothing. Same posture as `ClientErrors`. |
| `treat_missing_data` | `notBreaching` | No traceback is the healthy state; and `default_value = 0` means the healthy state is a real datapoint anyway. |
| channel | `intellichoice-staging-alerts` (**page**) | Users are affected — this is a served 500 — which is exactly the criterion `alerts_info` excludes. |

---

## 3. COLLECTOR-STATS-UNSCRAPED — before → after

### Before

`otelcol_exporter_*` in `IntelliChoice/intellichoice-staging/learning-api` and
`.../chat-api`: **none**. E6.2, §11: *"nothing scrapes it — the Prometheus receiver targets the
app port only. **No export success/failure rate exists anywhere in AWS.**"*

### The change

`terraform/modules/ecs-service/main.tf`, three edits to the collector config:

1. a second Prometheus scrape job, `${var.name}-collector`, 60s, `localhost:8888`;
2. four names added to the `filter/kpis` strict allowlist;
3. one `metric_declarations` block promoting those four on `dimensions = [["exporter"]]`.

**The metric names were measured, not read from documentation.** The pinned image
(`aws-otel-collector:v0.43.3`, collector core v0.117.0) was run locally with a `debug`-exporter
config and its `:8888` endpoint read from inside its own network namespace, because the endpoint
is a **loopback** bind and a published Docker port cannot reach it:

```
otelcol_exporter_send_failed_metric_points{exporter="debug",service_instance_id="...",service_name="aws-otel-collector",service_version="v0.43.3"} 0
otelcol_exporter_send_failed_spans{exporter="debug",...} 0
otelcol_exporter_sent_metric_points{exporter="debug",...} 1
otelcol_exporter_sent_spans{exporter="debug",...} 1
```

Two things that would otherwise have been guessed wrong:

- **No `_total` suffix.** E6.2 named the metrics without one and that turned out to be right,
  but the allowlist is `match_type = "strict"` — a guessed `_total` would have matched nothing,
  silently, and the failure would have looked exactly like "the scrape doesn't work".
- **`service_instance_id` is a UUID the collector regenerates on every start.** It is
  deliberately **not** a dimension: indexing it would mint a fresh set of CloudWatch series on
  every task replacement — unbounded cardinality on a metric added to make free failures
  visible. It remains an EMF field, readable when one task needs identifying.

`exporter` is the one label promoted, per the module's existing one-label discipline, and it is
the label that carries the answer: `awsxray` failing is a dark trace leg, `awsemf` failing is
every product KPI silently stopping.

Only these four counters were promoted. `metrics level: Normal` serves several dozen series
(queue sizes, per-receiver accept/refuse counts, process memory) and each is separately billed
once promoted; the allowlist was **not** widened beyond the export counters, and the known
SSE-metrics gap was left alone.

### After — read-back

The services were rolled at **2026-08-30T03:53:58Z** onto new task-definition revisions
(learning `:154`, chat `:152`) carrying the **same** application image `gha-5fa15d491057` that
was already running — verified against `describe-task-definition` before the roll. Both
rollouts reached `COMPLETED` with full desired counts (learning 2/2, chat 1/1) by 04:03:21Z.
The collectors restarted cleanly with **no scrape errors** in either `otel-collector` stream.

`aws cloudwatch list-metrics`, both namespaces:

```
IntelliChoice/intellichoice-staging/learning-api      IntelliChoice/intellichoice-staging/chat-api
  otelcol_exporter_sent_spans                 awsxray   otelcol_exporter_sent_spans                 awsxray
  otelcol_exporter_send_failed_spans          awsxray   otelcol_exporter_send_failed_spans          awsxray
  otelcol_exporter_sent_metric_points         awsemf    otelcol_exporter_sent_metric_points         awsemf
  otelcol_exporter_send_failed_metric_points  awsemf    otelcol_exporter_send_failed_metric_points  awsemf
```

Datapoints, 300-second periods, `Sum`, window 2026-08-30T03:40Z–04:05Z **UTC**:

| service | metric | exporter | 03:55:00Z | 04:00:00Z |
|---|---|---|---|---|
| learning-api | `otelcol_exporter_sent_spans` | awsxray | 28 | 40 |
| learning-api | `otelcol_exporter_send_failed_spans` | awsxray | **0** | **0** |
| learning-api | `otelcol_exporter_sent_metric_points` | awsemf | 302 | 380 |
| learning-api | `otelcol_exporter_send_failed_metric_points` | awsemf | **0** | **0** |
| chat-api | `otelcol_exporter_sent_spans` | awsxray | 12 | 20 |
| chat-api | `otelcol_exporter_send_failed_spans` | awsxray | **0** | **0** |
| chat-api | `otelcol_exporter_sent_metric_points` | awsemf | 150 | 190 |
| chat-api | `otelcol_exporter_send_failed_metric_points` | awsemf | **0** | **0** |

The first bucket is the roll minute itself, which is why it is partial. **This is the first time
an export success or failure rate has existed in AWS for this system.** The zeros are the
measured healthy baseline and they agree with E6.2's two windows.

### The alarm half (AUD-F-12)

Four alarms, one per (service × exporter), each on that leg's failure counter — routed to
**`intellichoice-staging-alerts-info`**, the quiet channel. The admission sentence is
`langsmith_ingest_failed`'s, verbatim in substance: the observability leg is dark while this is
firing and app traffic is unaffected — a student mid-exam notices nothing when a span fails to
reach X-Ray. Routing it to the page channel would put a diagnostic outage beside real ones at
2am, the exact unreadability D-401 split the topics to end. `test_alarm_severity_routing.py`'s
closed list records the decision rather than leaving it implicit; the alarm that **does** page
for this remediation is `unhandled_tracebacks`, which fires on a served 500.

Threshold `> 0` over 900s, from a measurement rather than a preference: E6.2 read
`send_failed_spans` over two staging windows and the baseline is exactly zero, and the exporters
retry internally before a failure is counted at all — so a counted failure is already a
retried-and-still-failed export.

**One limit, stated rather than hidden.** These alarms' own metric travels through `awsemf`,
which is one of the two things being watched. If `awsemf` dies entirely the metric stops
arriving and the alarms go quiet rather than firing. That is not closable from here — an alarm
cannot be delivered by the pipeline it monitors. `breaching` would not fix it either: it would
put both alarms into permanent ALARM whenever the services are idle enough to export nothing,
which on staging is most of the night. The condition "the collector stopped entirely" has a
different and now-available instrument: `otelcol_exporter_sent_spans` going flat, which is a
graphable metric for the first time, plus the ECS task-level alarms that see a container exit.

Deployed read-back, all six new alarms:

```
intellichoice-staging-learning-api-unhandled-tracebacks
  IntelliChoice/intellichoice-staging/learning-api/UnhandledTracebacks   dims=-
  GreaterThanThreshold 0  period=900s x1  missing=notBreaching  -> intellichoice-staging-alerts
intellichoice-staging-chat-api-unhandled-tracebacks
  IntelliChoice/intellichoice-staging/chat-api/UnhandledTracebacks       dims=-
  GreaterThanThreshold 0  period=900s x1  missing=notBreaching  -> intellichoice-staging-alerts
intellichoice-staging-learning-api-collector-awsxray-export-failures
  .../learning-api/otelcol_exporter_send_failed_spans          dims=exporter=awsxray
  GreaterThanThreshold 0  period=900s x1  missing=notBreaching  -> intellichoice-staging-alerts-info
intellichoice-staging-learning-api-collector-awsemf-export-failures
  .../learning-api/otelcol_exporter_send_failed_metric_points  dims=exporter=awsemf
  GreaterThanThreshold 0  period=900s x1  missing=notBreaching  -> intellichoice-staging-alerts-info
intellichoice-staging-chat-api-collector-awsxray-export-failures
  .../chat-api/otelcol_exporter_send_failed_spans              dims=exporter=awsxray
  GreaterThanThreshold 0  period=900s x1  missing=notBreaching  -> intellichoice-staging-alerts-info
intellichoice-staging-chat-api-collector-awsemf-export-failures
  .../chat-api/otelcol_exporter_send_failed_metric_points      dims=exporter=awsemf
  GreaterThanThreshold 0  period=900s x1  missing=notBreaching  -> intellichoice-staging-alerts-info
```

All four collector alarms evaluated to **OK** within two minutes of creation — they received
real `0` datapoints rather than sitting at `INSUFFICIENT_DATA`, which is itself evidence that
the scrape reached CloudWatch.

---

## 4. Terraform: what was applied, and what was deliberately not

`terraform validate` → `Success! The configuration is valid.` `terraform fmt -recursive`
rewrote nothing.

A full `terraform plan` showed **11 to add, 0 to change, 3 to destroy** — this task's ten
resources plus **one pre-existing drift that is not this task's**:
`module.ops_task.aws_ecs_task_definition.this` wants replacement because its image tag in state
(`gha-44a12dfc9549`) trails the variable (`gha-5fa15d491057`). **It was not applied.** Two
targeted applies were used instead, the standing §8 control-plane mechanism:

```
# apply 1 — no deploy needed, works on the currently deployed image
-target=module.observability.aws_cloudwatch_log_metric_filter.unhandled_tracebacks
-target=module.observability.aws_cloudwatch_metric_alarm.unhandled_tracebacks
-target=module.observability.aws_cloudwatch_metric_alarm.collector_export_failures
Plan: 8 to add, 0 to change, 0 to destroy.
Apply complete! Resources: 8 added, 0 changed, 0 destroyed.

# apply 2 — the collector config, same image
-target=module.ecs_service_learning_api.aws_ecs_task_definition.this
-target=module.ecs_service_chat_api.aws_ecs_task_definition.this
Plan: 2 to add, 0 to change, 2 to destroy.
Apply complete! Resources: 2 added, 0 changed, 2 destroyed.
```

The `2 to destroy` in apply 2 is the task-definition **replacement** pair, not a deletion of
anything running — ECS revisions are immutable, so terraform deregisters the old revision and
registers a new one.

**The services do not roll themselves.** `aws_ecs_service` carries
`lifecycle { ignore_changes = [task_definition, desired_count] }` (so CI deploys and terraform
do not fight), which means a new revision is inert until something points the service at it. So
both services were explicitly moved:

```
aws ecs update-service --cluster intellichoice-staging \
  --service intellichoice-staging-learning-api \
  --task-definition intellichoice-staging-learning-api:154 --force-new-deployment
```

**This is not a deploy.** Revision `:154`/`:152` carry `learning-api:gha-5fa15d491057` and
`chat-api:gha-5fa15d491057` — byte-identical image references to what was already running,
verified from `describe-task-definition` on the live revisions (`:153`/`:151`) *before* the
change. Only the collector's `AOT_CONFIG_CONTENT` differs. This is the D-455-mitigation-class
operation the Frozen Spec names.

The plan diff of `AOT_CONFIG_CONTENT`, per service, was exactly three hunks: the new scrape job,
the four allowlist names, the one `metric_declarations` block. Nothing else in either task
definition changed.

**A full `terraform plan` re-run after both applies reports `Plan: 1 to add, 0 to change,
1 to destroy`** — the `module.ops_task` image-tag drift, and nothing else. Every resource this
task touched is converged, and the one item left is exactly the one that was already there
before this task began.

---

## 5. State restored after the alarm test

The end-to-end filter test in §2b necessarily trips a real alarm on the page channel. Rather
than email the alert inbox, the alarm's actions were disabled for the test and restored
afterwards, with the restoration verified. The sequence, all UTC:

| time | action |
|---|---|
| 04:05:47Z | `disable-alarm-actions intellichoice-staging-learning-api-unhandled-tracebacks` → `ActionsEnabled: False` |
| 04:05:50Z | three synthetic events written to `r2-verification/synthetic-traceback` |
| 04:06:09Z | `UnhandledTracebacks` datapoint `04:05:00Z=1` observed |
| 04:07:05Z | alarm transitioned to `ALARM` — with actions disabled, so nothing was sent |
| 04:21:05Z | the synthetic datapoint left the 900-second evaluation window and the alarm returned to `OK` **on its own**, still with actions disabled — so no `OK` notification was sent either |
| 04:21:26Z | `enable-alarm-actions` — re-read as `OK / actions=True`, and `describe-alarms` across the whole account reports **no** alarm with actions disabled |

Re-enabling *after* the alarm had already cleared is the point of the ordering: had actions been
restored while it was still in `ALARM`, the eventual `ALARM → OK` transition would have sent an
`OK` mail to the alert inbox. Final state of all six new alarms:

```
OK  actions=True  intellichoice-staging-learning-api-unhandled-tracebacks
OK  actions=True  intellichoice-staging-chat-api-unhandled-tracebacks
OK  actions=True  intellichoice-staging-learning-api-collector-awsxray-export-failures
OK  actions=True  intellichoice-staging-learning-api-collector-awsemf-export-failures
OK  actions=True  intellichoice-staging-chat-api-collector-awsxray-export-failures
OK  actions=True  intellichoice-staging-chat-api-collector-awsemf-export-failures
```

The synthetic log stream is **left in place deliberately**: it is self-describing, it is the
audit trail for this verification, and deleting it would remove the evidence. It receives no
further events, so it cannot re-trip anything.

---

## 6. Cost

| item | count | note |
|---|---|---|
| CloudWatch metric filters | 2 | billed per custom metric, not per line scanned |
| CloudWatch custom metrics (log-derived) | 2 | `UnhandledTracebacks` × 2 services |
| CloudWatch custom metrics (EMF, collector) | 16 | 4 counters × 2 exporters-per-service is the ceiling; 8 series exist in practice (each failure counter appears only on the exporter that handles that signal type) |
| CloudWatch alarms | 6 | 2 page + 4 informational |
| paid model calls | **0** | |

The `filter/kpis` allowlist was deliberately not widened beyond the four export counters, which
is what keeps the EMF half of this bounded.

---

## 7. Verification summary

```
make lint      → All checks passed! / 481 files already formatted
make typecheck → 0 errors, 0 warnings, 0 informations
make test      → 2206 passed, 2 skipped, 1 xfailed in 520.75s (0:08:40)
```

Baseline before this task was `2200 passed, 3 skipped, 1 xfailed` (R1's recorded run). This task
adds **5 tests**; total collected rises 2203 → 2208, and one previously-skipped test passed this
run — the known draw-dependent flaky skip in learning-flow, which the Frozen Spec flags.

Terraform: `validate` clean; both targeted applies clean; the only plan item outside this task
(`module.ops_task`) was left untouched and remains as drift for whoever owns it.

---

## 8. What is still open after this task

- **The app-side `unhandled_exception` line is not in staging.** It reaches staging with the
  next manual deploy (D-417 §C9). Until then the staging signal for this class is the
  `UnhandledTracebacks` filter, which is why that filter was built to work on the current image
  and to keep working after the deploy.
- **The `-exc_info` exclusion is a coupling worth knowing about.** It depends on
  `JsonLogFormatter` continuing to name that field `exc_info`. If the field is ever renamed, the
  filter starts double-counting rather than breaking — a benign failure direction, but a silent
  one.
- **The collector alarms cannot see a total `awsemf` failure** (§3), by construction.
- **E6.2's two other findings are untouched by this task** and remain open as recorded there:
  `TRACE-ID-COLLISION` (0.14% of requests share an OTel `trace_id`) and
  `CHECKPOINTER-UNINSTRUMENTED` (no span represents LangGraph checkpoint I/O).
- **The known SSE-metrics allowlist gap is untouched**, per the Frozen Spec's boundary.

---

## 9. Files

**Product code (1):**
- `packages/observability/src/intellichoice_observability/request_logging.py` — `ERROR_LOGGER_NAME`
  / `ACCESS_LOGGER_NAME` constants; `_route_and_session_ids` extracted so both lines share the
  route-template and session-id-allowlist guarantees; `_log_unhandled_exception`; the middleware's
  `except Exception` block now names the exception and emits the second line before re-raising.

**Tests (2 files, +5 tests):**
- `packages/observability/tests/test_unhandled_exception_logging.py` (new) — the reproduction,
  the `trace_id` join, the redaction gate, the no-PII-key assertion, and the both-apps wiring
  assertion.
- `packages/observability/tests/test_alarm_severity_routing.py` — `collector_export_failures`
  added to the closed informational list, with its admission justification.

**Terraform (4 files):**
- `terraform/modules/ecs-service/main.tf` — the `localhost:8888` scrape job, four allowlist
  names, one `metric_declarations` block.
- `terraform/modules/observability/app_events.tf` — `unhandled_tracebacks` filter + alarm.
- `terraform/modules/observability/collector.tf` (new) — the four export-failure alarms.
- `terraform/modules/observability/variables.tf` — `unhandled_traceback_alarm_threshold`,
  `otel_collector_services`, `collector_export_failure_alarm_threshold`.
- `terraform/environments/staging/main.tf` — `otel_collector_services = ["learning-api", "chat-api"]`.

**New artifacts (not product):** this file, plus
`raw/R2_prefix_failing_tests.txt` (the pre-fix failing run) and
`raw/R2_test_metric_filter.json` (the filter-pattern validation against real event text).
