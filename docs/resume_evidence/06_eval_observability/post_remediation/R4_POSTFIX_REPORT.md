# R4 — PII-REDACTION-GAPS F-1 + F-2: fixes and post-fix re-measurement

**Remediation task R4** of the post-measurement program (user-commissioned 2026-08-29), against
the two cheap, high-value gaps E6.1 measured (D-458):

- **F-1** — `_URL_RE` in `packages/shared/src/intellichoice_shared/pii_redaction.py` was compiled
  without `re.IGNORECASE`, so `HTTP://`, `Https://` and `WWW.` matched nothing at all.
- **F-2** — the span-export credential redactor in
  `packages/observability/src/intellichoice_observability/tracing.py` named
  `token|access_token|api_key` as query parameters and `[Bb]earer` as an auth scheme, while the
  *log* denylist already listed `refresh_token`, `id_token`, `oauth_token` and `bearer_token` as
  keys. Two credential vocabularies had drifted apart.

Reproduce → smallest fix → permanent regression tests → re-run the frozen corpus → update the
permanent lane's recorded gates.

**$0, fully offline.** No model call, no network, no database, no AWS, no Docker. The three
layers under measurement are pure functions plus an in-memory OpenTelemetry exporter.

**Nothing in this task replaces an E6.x artifact.** `E6_1_REPORT.md`, `pii_probe_results.json`
and `pii_probe_metrics.csv` in the parent directory are the 2026-08-28 measurement at `7a486a9`
and are untouched — verified with `git status docs/resume_evidence/` (§6). The corpus itself
(`benchmarks/resume_evidence/06_eval_observability/pii_probe_corpus.py`) is untouched too: the
denominators below are the *same* 651 text cases (277 in-contract / 110 out-of-contract / 264
negative) and the same 46 span cases (22 of them credential probes) E6.1 scored.

**Out of scope, deliberately.** F-3 (paren-phone `(555)123-4567`), F-4 (exotic email syntax),
F-5 (the `name`-key nuance) and E6.1's over-capture cosmetics (a URL eating a trailing `"}`, an
email swallowing a sentence-final period) were not touched. They are priced trade-offs or need
design discussion; they remain open in the register.

---

## 1. What was wrong, in one paragraph each

**F-1.** Scheme names and host labels are case-insensitive by RFC 3986, and a phone keyboard
autocapitalises the first word of a message — which is exactly where a student pastes a link.
`re.compile(r"https?://\S+|www\.\S+")` is case-*sensitive*, so `Https://example.org/help` and
`Www.example.org/help` were not URLs as far as the redactor was concerned. E6.1 measured this
as 6/6 of the `url_uppercase_scheme` category disagreeing with its label: URL recall 68/74. The
same three compiled patterns are shared by `contains_pii_pattern`, the S25 memory-consolidation
denylist screen, so the gap was two call sites wide — a model-generated fact holding
`Www.example.org` was not dropped either. One flag fixes both.

**F-2.** The span redactor's job is credentials, not PII (AUD-F-13, DRIFT-82): token-bearing
query parameters, bare JWTs, `Bearer` values, stripped at the export boundary. Its query-param
alternation named three parameters; the log denylist named six credential keys. The two lists
were written at different times by different tasks and nothing held them together, so
`?refresh_token=` and `?id_token=` were denylisted as log keys and exported verbatim in a span.
The gap stayed quiet because the *usual* value of such a parameter is a JWT, which the separate
JWT pattern catches — only an opaque token exposed it. `BEARER` uppercased is the same shape of
mistake: HTTP auth schemes are case-insensitive by RFC 7235, so `BEARER abc123XYZ` is the same
credential, and `[Bb]earer` said otherwise. E6.1 measured span credential recall 18/22.

---

## 2. Reproduction — the five tests, failing before the fix

Written against the unfixed product code (raw: `raw/R4_prefix_failing_tests.txt`, produced by
reverting only the two product files to `HEAD` while keeping the new tests):

```
FAILED packages/shared/tests/test_pii_redaction.py::test_redacts_urls_whose_scheme_or_host_label_is_capitalised
FAILED packages/shared/tests/test_pii_redaction.py::test_uppercase_urls_are_screened_by_the_consolidation_denylist_too
FAILED packages/observability/tests/test_tracing.py::test_uppercase_bearer_credentials_are_redacted_before_export
FAILED packages/observability/tests/test_tracing.py::test_refresh_and_id_token_query_parameters_are_redacted_before_export
FAILED packages/observability/tests/test_tracing.py::test_the_span_credential_vocabulary_covers_the_log_denylist_credential_keys
5 failed, 17 passed in 0.29s
```

Two further tests were added and **pass in both directions** on purpose — they are the
false-positive arm, not the reproduction:
`test_the_url_near_misses_stay_untouched_after_the_case_widening` (the corpus's
`neg_near_miss_url` shapes, uppercased) and
`test_clean_operational_attributes_survive_the_widened_credential_patterns`
(`db.statement`, `http.route`, a model id, `token_count`, and `refresh_token`/`id_token` used as
words in prose with no `?`/`&` context). Widening a pattern is only safe if what was
deliberately *not* matched still is not, and a guard that only starts passing after the change
proves nothing about the change.

## 3. The fixes

**F-1** — one flag, plus a comment saying why it is load-bearing:

```
_URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
```

The email and phone patterns were checked and deliberately left alone: `\w` and `\d` are
already case-blind, so `re.IGNORECASE` would change nothing there, and changing a pattern that
does not need it is diff for its own sake.

**F-2** — the vocabulary is now a named constant in `tracing.py`, and the reconciliation with
the log denylist is asserted by a test rather than promised by a comment:

```
_CREDENTIAL_QUERY_PARAMS: tuple[str, ...] = (
    "access_token", "api_key", "bearer_token", "id_token",
    "oauth_token", "refresh_token", "token",
)
```

`test_the_span_credential_vocabulary_covers_the_log_denylist_credential_keys` derives the
credential half of `logging_config._DENYLISTED_LOG_KEYS` and requires it to be a subset of
`_CREDENTIAL_QUERY_PARAMS`. That is the test that fails the next time one list grows without the
other — the failure mode that produced F-2 in the first place. It also carries a vacuity guard,
so it cannot pass by finding no credential keys at all.

The constant is deliberately **not** an import of `_DENYLISTED_LOG_KEYS`. That set is a denylist
of log-record *keys* and also names PII fields (`email`, `prompt`, `transcript`), which are not
URL parameters and are explicitly outside this layer's credential-only scope. Sharing one object
would hand each layer the other's semantics — the span redactor would start claiming to be a PII
redactor, which E6.1's scope statement spends a paragraph saying it is not.

The `Bearer` pattern became `re.compile(r"(bearer\s+)\S+", re.IGNORECASE)`. The capture group
keeps the original spelling and only the value is replaced, so `BEARER abc123XYZ` exports as
`BEARER REDACTED` and the existing `Bearer REDACTED` assertions are unaffected.

The query-parameter pattern keeps its `[?&]` anchor. That anchor is what keeps it off ordinary
prose and off `db.statement`, and it is why one E6.1 span miss is **left as measured** — see §5.

## 4. Before → after, on the same corpus

Corpus unchanged: 651 text cases (277 in-contract, 110 out-of-contract, 264 negative), 49 log
keys, 46 span cases (22 credential probes). Raw stdout: `raw/R4_harness_before.txt`,
`raw/R4_harness_after.txt`. Full machine-readable metrics: `pii_probe_metrics_postfix.csv`
(same 51 rows, same schema as the E6.1 CSV) and `raw/pii_probe_results_postfix.json`.

### Layer 1 — the regex redactor (`redact_free_text`)

| metric | before | after | Δ |
|---|---|---|---|
| overall precision | 261/269 = 97.03% | **267/275 = 97.09%** | +0.07 pp |
| overall recall | 261/277 = 94.22% | **267/277 = 96.39%** | **+2.17 pp** |
| overall F1 | 522/546 = 95.60% | **534/552 = 96.74%** | +1.14 pp |
| precision excl. adversarial negatives | 261/261 = 100% | **267/267 = 100%** | — |
| false positives | 8/264 = 3.03% | **8/264 = 3.03%** | **0 new** |
| false negatives | 16/277 | **10/277** | −6 |

Per class:

| class | recall before | recall after | precision before | precision after |
|---|---|---|---|---|
| email | 119/125 = 95.2% | 119/125 = 95.2% | 119/119 = 100% | 119/119 = 100% |
| **url** | 68/74 = 91.9% | **74/74 = 100%** | 68/68 = 100% | **74/74 = 100%** |
| phone | 62/66 = 93.9% | 62/66 = 93.9% | 62/70 = 88.6% | 62/70 = 88.6% |
| mixed | 12/12 = 100% | 12/12 = 100% | — | — |

**The precision denominator moves from 269 to 275 and that is not a denominator change.** It is
`true positives + false positives`, not the negative count. The false-positive count is
identical (8), the negative half is identical (264 cases), and the six newly-caught URL
positives are what raised the denominator. The corpus composition is byte-identical; a rebuild
of the corpus is asserted deterministic by the permanent lane.

### Layer 2 — the JSON log formatter

D-394 routes `message` and `exc_info` through layer 1's regexes rather than a second copy, so
both confusion matrices track layer 1 exactly, and still do:
recall 261/277 → **267/277**, precision 261/269 → **267/275**, on both fields.
Denylist-key coverage 36/36 and control keys surviving 12/12 are unchanged — this task did not
touch that layer, and the numbers say so.

### Layer 3 — the span-export credential redactor

| metric | before | after |
|---|---|---|
| credential recall | 18/22 = 81.8% | **21/22 = 95.5%** |
| credential precision | 18/18 = 100% | **21/21 = 100%** |
| clean operational attributes altered | 0/16 | **0/16** |
| student PII redacted at this layer | 0/8 (by design) | 0/8 (by design) |

### Exactly which cases moved

Nine, and only nine. Six text cases, all `url_uppercase_scheme`:

| case | text | before | after |
|---|---|---|---|
| `url_uppercase_scheme-001` | `HTTP://EXAMPLE.ORG/help` | verbatim | `[redacted-url]` |
| `url_uppercase_scheme-002` | `HTTPS://EXAMPLE.ORG` | verbatim | `[redacted-url]` |
| `url_uppercase_scheme-003` | `Https://example.org/help` | verbatim | `[redacted-url]` |
| `url_uppercase_scheme-004` | `Http://school.example` | verbatim | `[redacted-url]` |
| `url_uppercase_scheme-005` | `WWW.EXAMPLE.ORG` | verbatim | `[redacted-url]` |
| `url_uppercase_scheme-006` | `Www.example.org/help` | verbatim | `[redacted-url]` |

and three span cases:

| case | attribute | before | after |
|---|---|---|---|
| `span_bearer_uppercase-001` | `http.request.header.authorization` | `BEARER abc123XYZ` | `BEARER REDACTED` |
| `span_credential_gap-002` | `auth.refresh` | `?refresh_token=abc123XYZ` | `?refresh_token=REDACTED` |
| `span_credential_gap-003` | `auth.id` | `?id_token=abc123XYZ` | `?id_token=REDACTED` |

Every other one of the 651 text cases and 46 span cases produced a byte-identical result before
and after (diffed case-by-case from the two `pii_probe_results.json` files). That is the strong
form of "no collateral": not "precision did not drop", but "no other case changed at all".

## 5. What is still missed, and why

**10 in-contract text misses** remain, and they are exactly E6.1's F-4 and F-3, unchanged:

- `email_exotic_syntax` × 6 — quoted local parts, address literals, a double `@`, a TLD-less
  host. **F-4, out of scope by the task's decision boundaries.**
- `phone_parens_nospace` × 4 — `(555)123-4567`, where the separator after the area code is
  mandatory in the pattern. **F-3, out of scope.**

**8 false positives** remain, all `neg_phone_shaped_identifier`: SKUs, lot and invoice numbers
that genuinely carry a punctuated 3-3-4 grouping. Not a defect — the documented, priced
trade-off of having a phone class at all, and the reason precision is reported twice.

**1 span credential miss** remains: `span_credential_gap-001`, `token=abc123XYZ` with no `?` or
`&` in front of it. This one is **deliberately not fixed.** Dropping the `[?&]` anchor is what
would catch it, and that anchor is the only thing keeping the pattern off `db.statement`,
`http.route` and ordinary prose — a span store whose SQL and route attributes are corrupted is
worse than one carrying a bare `token=` with no URL around it. That is a semantics change, not a
vocabulary fix, and the task's decision boundaries put it out of scope. It is recorded here as
the one known remaining miss rather than quietly rounded away; the comment above `_REDACTIONS`
says the same thing in the code.

## 6. Verification

Reproduction and re-measurement (raw: `raw/R4_postfix_tests.txt`):

```
uv run pytest packages/shared/tests/test_pii_redaction.py packages/observability/tests/test_tracing.py packages/observability/tests/test_pii_probe_corpus.py -q
54 passed in 0.36s
```

Full suite, `make lint typecheck test`:

```
uv run ruff check .        -> All checks passed!
uv run ruff format --check .  -> 484 files already formatted
uv run pyright             -> 0 errors, 0 warnings, 0 informations
uv run pytest              -> 2226 passed, 2 skipped, 1 xfailed in 523.26s
```

The pre-task baseline was **2219 passed, 2 skipped, 1 xfailed**; this task adds exactly the
seven tests listed in §10, and the skip and xfail counts are unchanged — no test was disabled to
make anything pass. (The known draw-dependent learning-flow flake did not fire in this run.)

The permanent lane's `RECORDED` constants were updated to the new measurement in the same
change. That is the lane's designed workflow, documented in its own module docstring: the
constants are a recorded measurement, not a chosen threshold, and improving the behaviour
without re-recording would leave the gate protecting a number that no longer describes the
system. The gates stay one-directional and zero-tolerance, so a regression below the *new*
values still fails.

| gate | was | now |
|---|---|---|
| `layer1/overall/precision` | 261/269 | 267/275 |
| `layer1/overall/recall` | 261/277 | 267/277 |
| `layer1/overall/f1` | 522/546 | 534/552 |
| `layer1/overall_excl_adversarial_negatives/precision` | 261/261 | 267/267 |
| `layer1/class:url/recall` | 68/74 | 74/74 |
| `layer1/class:url/precision` | 68/68 | 74/74 |
| `layer2/message_field/recall` | 261/277 | 267/277 |
| `layer2/message_field/precision` | 261/269 | 267/275 |
| `layer2/exc_info_field/recall` | 261/277 | 267/277 |
| `layer2/exc_info_field/precision` | 261/269 | 267/275 |
| `layer3/credentials/recall` | 18/22 | 21/22 |
| `layer3/credentials/precision` | 18/18 | 21/21 |

The other eight `RECORDED` entries (email and phone rates, `class:mixed`, API consistency,
layer 2's denylist and control keys) are unchanged, which is itself the evidence that this
change stayed inside its blast radius.

Positive controls: **11/11 fired**, before and after. Nothing above is trusted from a redactor
whose patterns cannot be shown to fire (the AUD-F-12 lesson).

Determinism: the harness was run twice post-fix and the metrics CSV was byte-identical, which is
what makes a zero-tolerance gate legitimate.

**Historical artifacts untouched.** `git status --short docs/resume_evidence/` reports no
modification to `E6_1_REPORT.md`, `E6_2_REPORT.md`, `pii_probe_results.json`,
`pii_probe_metrics.csv`, `trace_coverage_results.json` or `trace_coverage_summary.csv`; the only
new paths under `06_eval_observability/` are this file, `pii_probe_metrics_postfix.csv` and the
four `raw/R4_*` files.

## 7. Blast radius

`redact_free_text` has 8 production call sites (student chat before the Bedrock wire and before
persistence, D-072; the S25 consolidation screen; D-394's `message` and `exc_info` log routing).
All of them get strictly *more* redaction of one shape — an uppercase URL — and nothing else:
the case-by-case diff in §4 shows no other input changing. `RedactingSpanExporter` sits on both
`build_tracer_provider` branches, so the span change reaches production and the in-memory test
exporter identically; the clean-attribute arm measures that operational spans still arrive
intact.

## 8. Reproducing

```
uv run python benchmarks/resume_evidence/06_eval_observability/pii_probe_harness.py --out-dir /tmp/x
uv run pytest packages/observability/tests/test_pii_probe_corpus.py -q
```

Note that the harness writes `E6_1_REPORT.md` / `pii_probe_metrics.csv` / `pii_probe_results.json`
into its `--out-dir`, which defaults to the parent directory. **Pass `--out-dir` when re-running
for R4 purposes**, then copy, so the 2026-08-28 E6.1 artifacts are never overwritten — that is
how the copies in this directory were produced.

## 9. Provenance

- Original measurement: `E6_1_REPORT.md`, repository `7a486a9`, 2026-08-28.
- This re-measurement: 2026-08-30, working tree at `a2b579a` **plus this task's uncommitted
  edits** — the `git_sha` recorded inside `pii_probe_metrics_postfix.csv`'s sibling JSON is
  `a2b579acb0377614c086c428cf7e4507f29f20b9`, which is the parent commit, because the harness
  reads `git rev-parse HEAD` and the fix was not yet committed when it ran. The five changed
  files are listed in §10; the numbers here describe the tree with those five files applied, not
  `a2b579a` alone.
- Environment: local, offline, $0 — no model call, no network, no database, no AWS.

## 10. Files changed

| file | change |
|---|---|
| `packages/shared/src/intellichoice_shared/pii_redaction.py` | `re.IGNORECASE` on `_URL_RE` + rationale comment |
| `packages/observability/src/intellichoice_observability/tracing.py` | `_CREDENTIAL_QUERY_PARAMS` constant, widened query-param alternation, case-insensitive `bearer`, reconciliation comment |
| `packages/shared/tests/test_pii_redaction.py` | 3 tests (2 reproduction, 1 false-positive arm) |
| `packages/observability/tests/test_tracing.py` | 4 tests (3 reproduction incl. the vocabulary-reconciliation assertion, 1 false-positive arm) |
| `packages/observability/tests/test_pii_probe_corpus.py` | `RECORDED` updated to the new measurement; docstring provenance; a comment recording what moved |
