# E6.1 - PII-redaction precision/recall over a labeled synthetic probe corpus

> Experiment: **E6.1** of `docs/resume_evidence/MEASUREMENT_PLAN.md` (Theme 6).
> Generated: **2026-08-29T03:24:19.994332+00:00** at repository `7a486a9d8ad6a3affb93c14830b58ff4aa353d26`.
> Environment: **local, offline, $0 - no model call, no network, no database**.
> Cost of this measurement: **$0** - no model call, no network, no database, no AWS.
> Harness: `benchmarks/resume_evidence/06_eval_observability/pii_probe_harness.py`.
> Corpus: `benchmarks/resume_evidence/06_eval_observability/pii_probe_corpus.py`.
> Permanent lane: `packages/observability/tests/test_pii_probe_corpus.py`.

## 1. What this measures, and what it does not

Before this run the repository had **no** labeled PII corpus, **no** negative corpus and **no** precision or recall number for redaction anywhere. The redactor had five direct unit tests (three positive, two negative) and `contains_pii_pattern` had none. The live scanners (`make scan-logs`, `make scan-traces`) carry 47 needles but are all-positive scans of a deployed store: they answer *is the store clean?*, never *how good is the redactor?*

Three callable layers are driven offline over one labeled corpus. Each layer's scope is stated before its numbers, because the three do different jobs and the aggregate of a scope confusion is worse than no number at all.

| layer | code under measurement | scope |
|---|---|---|
| 1 | `intellichoice_shared.pii_redaction` | email, http(s)/`www.` URL, punctuated 3-3-4 phone. **No name detection, by design.** |
| 2 | `intellichoice_observability.logging_config` | exact-match denylist over top-level `extra=` keys, plus D-394's free-text routing of `message`/`exc_info` through layer 1 |
| 3 | `intellichoice_observability.tracing.RedactingSpanExporter` | **credentials** (token query params, JWTs, `Bearer` values) on span attributes and events |

**Names, addresses, birth dates and student IDs are not measured as recall here, and no number below should be read as covering them.** They are governed by a different mechanism - the structural payload allowlist, whose own evidence is the 59 reflection-driven payload-governance tests and the 47-needle live scanners - and by the absolute rule that Postgres stores no student PII at all (SPEC §5.30). This experiment does not re-measure that layer. It does measure how much such PII the regex layer catches anyway (§5), because the honest number there is not zero.

## 2. The corpus

- **651 labeled free-text cases** across 75 categories, every value synthetic.
- **277 in-contract positives** - real email/URL/3-3-4-phone forms the module documents itself as covering. The recall denominator.
- **110 out-of-contract positives** - real PII the module states it does not attempt. In neither denominator; reported in §5.
- **264 negatives** - no PII of any kind. The precision denominator.
- Plus **49 log-key cases** (layer 2) and **46 span cases** (layer 3).

Generation is deterministic: fixed value pools, fixed sentence templates, fixed order, no randomness and no I/O, so `build_corpus()` is byte-identical on any machine - which is what lets the pytest lane gate on an exact rate. Labels encode the module's *documented contract* and were fixed before the measurement ran; they are never derived from observed behaviour, or the experiment would score the implementation against itself and report 100% by construction.

**Disjoint from the live scanners on purpose.** `scan_logs_pii.py` and `scan_xray_pii.py` build their needles from `mysql_fixtures.py` - seeded display names, manager emails, branch addresses, branch coordinates. This corpus shares no value with that set. The two instruments answer different questions, and an overlapping corpus would let one instrument's blind spot hide inside the other's result.

### 2.1 Why three labels rather than two

A two-way positive/negative split cannot describe this redactor honestly. Scoring a missed name as a recall failure would measure the module against a contract it never accepted; dropping names from the corpus would hide the residual risk the module explicitly documents. The third label - `out_of_contract` - keeps both visible: such cases are excluded from recall *and* from precision, and printed in their own table in §5.

## 3. Positive controls

**11/11 controls fired.** Every pattern in every layer is proved able to fire before any clean result below is trusted - the `scripts/scan_xray_pii.py` convention, and the direct lesson of AUD-F-12, where an empty trace store certified "no PII" for an hour.

| control | fired |
|---|---|
| `layer1_email` | yes |
| `layer1_url` | yes |
| `layer1_phone` | yes |
| `layer1_contains` | yes |
| `layer2_denylist` | yes |
| `layer2_message` | yes |
| `layer2_exc_info` | yes |
| `layer3_query_token` | yes |
| `layer3_jwt` | yes |
| `layer3_bearer` | yes |
| `layer3_event` | yes |

## 4. Layer 1 - the regex redactor

> Scope: intellichoice_shared.pii_redaction implements exactly three classes - email, http(s)/www. URL, punctuated 3-3-4 phone. Name detection is deliberately not attempted (module docstring, SPEC §5.30.1); names and opaque identifiers are governed by the structural payload-allowlist layer, which this experiment does not re-measure.

| metric | n/N |
|---|---|
| **Precision** (negatives only) | 261/269 (97.0%) |
| **Recall** (in-contract positives only) | 261/277 (94.2%) |
| **F1** | 522/546 (95.6%) |
| Precision excluding the adversarial negative subgroup | 261/261 (100.0%) |
| False negatives | 16/277 (5.8%) of in-contract positives |
| False positives | 8/264 (3.0%) of negatives |

Per class:

| class | recall (any pattern) | recall (own pattern) | precision |
|---|---|---|---|
| email | 119/125 (95.2%) | 119/125 (95.2%) | 119/119 (100.0%) |
| url | 68/74 (91.9%) | 68/74 (91.9%) | 68/68 (100.0%) |
| phone | 62/66 (93.9%) | 62/66 (93.9%) | 62/70 (88.6%) |
| mixed (several classes in one message) | 12/12 (100.0%) | - | - |

"Own pattern" is stricter than "any pattern": a case counts only when its own class's marker fired, so a positive rescued by a *different* pattern shows as a miss for its own class instead of being silently credited. The two columns agree everywhere in this corpus, including the URLs carrying an address in their userinfo section (`https://ada.k@example.org/path`), where the email pattern runs first and the URL pattern then swallows its output - the URL marker is what survives, so the URL class is correctly credited.

### 4.1 Before/after

Run through the identity function (no redaction), **277/277 (100.0%)** in-contract positives leak. Through `redact_free_text`, **16/277 (5.8%)** leak. That is the before/after this experiment can measure directly; it says nothing about how often such text occurs in real traffic, which this corpus cannot and does not claim.

### 4.2 API consistency

`contains_pii_pattern` agrees with `redact_free_text` on **651/651 (100.0%)** cases. They share the three compiled patterns, so any disagreement would be a defect rather than a measurement. `contains_pii_pattern` had no direct test before this run - it is the S25 memory-consolidation denylist screen, so a silent divergence there would let a model-generated fact carrying PII be stored.

### 4.3 Per category

| category | contract | cases | redacted | agrees with label |
|---|---|---:|---:|---|
| `email_exotic_syntax` | in_contract | 8 | 2 | 2/8 |
| `email_in_json` | in_contract | 6 | 6 | 6/6 |
| `email_in_korean` | in_contract | 9 | 9 | 9/9 |
| `email_in_sentence` | in_contract | 24 | 24 | 24/24 |
| `email_plain` | in_contract | 48 | 48 | 48/48 |
| `email_subaddressed` | in_contract | 18 | 18 | 18/18 |
| `email_unicode` | in_contract | 6 | 6 | 6/6 |
| `email_uppercase` | in_contract | 6 | 6 | 6/6 |
| `mixed_multi_class` | in_contract | 12 | 12 | 12/12 |
| `phone_country_prefix` | in_contract | 8 | 8 | 8/8 |
| `phone_dashes` | in_contract | 8 | 8 | 8/8 |
| `phone_dots` | in_contract | 8 | 8 | 8/8 |
| `phone_in_json` | in_contract | 4 | 4 | 4/4 |
| `phone_in_korean` | in_contract | 3 | 3 | 3/3 |
| `phone_in_sentence` | in_contract | 6 | 6 | 6/6 |
| `phone_mixed_separators` | in_contract | 4 | 4 | 4/4 |
| `phone_multiple` | in_contract | 3 | 3 | 3/3 |
| `phone_parens_nospace` | in_contract | 4 | 0 | 0/4 |
| `phone_parens_space` | in_contract | 6 | 6 | 6/6 |
| `phone_spaces` | in_contract | 8 | 8 | 8/8 |
| `phone_tollfree` | in_contract | 4 | 4 | 4/4 |
| `url_http_plain` | in_contract | 6 | 6 | 6/6 |
| `url_https_plain` | in_contract | 6 | 6 | 6/6 |
| `url_in_json` | in_contract | 4 | 4 | 4/4 |
| `url_in_korean` | in_contract | 4 | 4 | 4/4 |
| `url_in_sentence` | in_contract | 12 | 12 | 12/12 |
| `url_trailing_punctuation` | in_contract | 5 | 5 | 5/5 |
| `url_uppercase_scheme` | in_contract | 6 | 0 | 0/6 |
| `url_userinfo` | in_contract | 3 | 3 | 3/3 |
| `url_with_fragment` | in_contract | 4 | 4 | 4/4 |
| `url_with_path` | in_contract | 8 | 8 | 8/8 |
| `url_with_port` | in_contract | 4 | 4 | 4/4 |
| `url_with_query_token` | in_contract | 6 | 6 | 6/6 |
| `url_www_bare` | in_contract | 6 | 6 | 6/6 |
| `neg_clock_time` | negative | 8 | 0 | 8/8 |
| `neg_code_snippet` | negative | 12 | 0 | 12/12 |
| `neg_coordinates` | negative | 8 | 0 | 8/8 |
| `neg_currency` | negative | 10 | 0 | 10/10 |
| `neg_date` | negative | 15 | 0 | 15/15 |
| `neg_decimal` | negative | 10 | 0 | 10/10 |
| `neg_equation_steps` | negative | 10 | 0 | 10/10 |
| `neg_external_id` | negative | 10 | 0 | 10/10 |
| `neg_file_path` | negative | 8 | 0 | 8/8 |
| `neg_fraction` | negative | 10 | 0 | 10/10 |
| `neg_iso_timestamp` | negative | 10 | 0 | 10/10 |
| `neg_math_expression` | negative | 20 | 0 | 20/20 |
| `neg_measurement` | negative | 8 | 0 | 8/8 |
| `neg_module_path` | negative | 6 | 0 | 6/6 |
| `neg_near_miss_email` | negative | 12 | 0 | 12/12 |
| `neg_near_miss_phone` | negative | 12 | 0 | 12/12 |
| `neg_near_miss_url` | negative | 12 | 0 | 12/12 |
| `neg_percent` | negative | 6 | 0 | 6/6 |
| `neg_phone_shaped_identifier` | negative | 8 | 8 | 0/8 |
| `neg_prose_en` | negative | 15 | 0 | 15/15 |
| `neg_prose_ko` | negative | 15 | 0 | 15/15 |
| `neg_prose_mixed` | negative | 10 | 0 | 10/10 |
| `neg_scientific` | negative | 6 | 0 | 6/6 |
| `neg_sports_score` | negative | 5 | 0 | 5/5 |
| `neg_uuid` | negative | 8 | 0 | 8/8 |
| `neg_version` | negative | 10 | 0 | 10/10 |
| `oos_bare_domain` | out_of_contract | 8 | 0 | 8/8 |
| `oos_birth_date` | out_of_contract | 8 | 0 | 8/8 |
| `oos_ip_address` | out_of_contract | 4 | 0 | 4/4 |
| `oos_name_english` | out_of_contract | 10 | 0 | 10/10 |
| `oos_name_korean` | out_of_contract | 8 | 0 | 8/8 |
| `oos_national_id` | out_of_contract | 6 | 0 | 6/6 |
| `oos_other_scheme` | out_of_contract | 8 | 1 | 7/8 |
| `oos_phone_extension` | out_of_contract | 4 | 0 | 4/4 |
| `oos_phone_international` | out_of_contract | 10 | 0 | 10/10 |
| `oos_phone_korean_landline` | out_of_contract | 6 | 3 | 3/6 |
| `oos_phone_korean_mobile` | out_of_contract | 8 | 0 | 8/8 |
| `oos_phone_unpunctuated` | out_of_contract | 8 | 0 | 8/8 |
| `oos_social_handle` | out_of_contract | 4 | 0 | 4/4 |
| `oos_street_address` | out_of_contract | 10 | 0 | 10/10 |
| `oos_student_id` | out_of_contract | 8 | 0 | 8/8 |

## 5. The out-of-scope table

Real PII the module states it does not attempt. **None of it is counted as a recall failure** - and where the regex catches some anyway, none of it is counted as a true positive either.

Caught anyway: **4/110 (3.6%)**.

| category | cases | caught anyway |
|---|---:|---:|
| `oos_bare_domain` | 8 | 0 |
| `oos_birth_date` | 8 | 0 |
| `oos_ip_address` | 4 | 0 |
| `oos_name_english` | 10 | 0 |
| `oos_name_korean` | 8 | 0 |
| `oos_national_id` | 6 | 0 |
| `oos_other_scheme` | 8 | 1 |
| `oos_phone_extension` | 4 | 0 |
| `oos_phone_international` | 10 | 0 |
| `oos_phone_korean_landline` | 6 | 3 |
| `oos_phone_korean_mobile` | 8 | 0 |
| `oos_phone_unpunctuated` | 8 | 0 |
| `oos_social_handle` | 4 | 0 |
| `oos_street_address` | 10 | 0 |
| `oos_student_id` | 8 | 0 |

The catches are incidental and worth naming so nobody reads them as coverage: Korean landline numbers with a three-digit area code (`031-123-4567`) happen to be 3-3-4, and `mailto:` addresses are caught by the *email* pattern rather than by any URL handling. Korean **mobile** numbers - the format this product's actual users have - are 3-4-4 and are caught **0/8**.

## 6. Layer 2 - the JSON log formatter and the denylist filter

> Scope: Two mechanisms, measured separately. PiiDenylistFilter is an exact-match denylist over top-level `extra=` KEYS (D-011's precedent) - it sees structure, never text. D-394 added free-text routing of the interpolated `message` and of `exc_info` through layer 1's regexes, so those two fields inherit layer 1's scope and layer 1's limits exactly.

| measurement | n/N |
|---|---|
| Denylisted `extra=` keys redacted (of those reachable) | 36/36 (100.0%) |
| Denylisted keys reachable through `extra=` at all | 36/37 (97.3%) |
| Control keys surviving unchanged | 12/12 (100.0%) |
| `message` field - recall | 261/277 (94.2%) |
| `message` field - precision | 261/269 (97.0%) |
| `exc_info` field - recall | 261/277 (94.2%) |
| `exc_info` field - precision | 261/269 (97.0%) |

The control-keys row exists so the denylist number cannot be gamed: a filter that redacted every field would score full coverage, so operationally necessary fields (`session_id`, `question_id`, `skill_name`, `model_id`, `latency_ms`, `cost_cents`, …) are measured for survival at the same time.

`message` and `exc_info` inherit layer 1's regexes exactly, so they inherit layer 1's limits exactly - the rates match §4 case for case. That is the intended design (D-394 deliberately reuses one shared regex set rather than growing a second copy that would drift), and it means every finding in §8 applies to the log path too.

### 6.1 A dead entry in the denylist

**F-5 (documentation-level, no leak).** `name` is on the 37-key denylist but cannot be set through `extra=` at all: `Logger.makeRecord` raises `KeyError: "Attempt to overwrite 'name' in LogRecord"` for any standard record attribute, before the filter runs. So it neither leaks nor gets redacted through the ordinary call path, and the reachable denylist is 36 keys, all of them covered. Nothing to fix in behaviour; worth knowing, because a reader of that list would reasonably believe a `name` field passed by a call site would be filtered, and the actual reason it is safe is that the standard library refuses the field, not that this filter catches it. (`student_name`, `parent_name`, `guardian_name`, `display_name`, `full_name`, `first_name` and `last_name` are all reachable and all covered.)

### 6.2 The two documented gaps, priced

- **`event` holds `record.msg` verbatim when it is a `str`**: 277/277 (100.0%) in-contract positives survive into the `event` field when a call site passes an f-string. This is deliberate - `event` is the static template an operator groups by, and interpolating it was D-394's *original* defect (unbounded cardinality plus free text). The exposure is real but is bounded by a call-site rule, and D-394's AST sweep found exactly one f-string call site.
- **The filter checks top-level keys only**: 40/40 (100.0%) probed values nested one level deep under an innocuous key (`extra={"payload": {"email": …}}`) survive. The module docstring states this (D-011's exact-match precedent) and requires call sites to keep `extra=` flat. Measured here so "documented" is also "quantified".

## 7. Layer 3 - the span-export redactor

> Scope: RedactingSpanExporter strips CREDENTIALS - token-bearing query parameters, bare JWTs, `Bearer` values - from span attributes, event names and event attributes at the export boundary (AUD-F-13, DRIFT-82). It is not a PII redactor and does not claim to be: student PII in a span passes through untouched, which is measured below rather than assumed.

| measurement | n/N |
|---|---|
| Credential recall | 18/22 (81.8%) |
| Credential precision | 18/18 (100.0%) |
| Clean operational attributes altered | 0/16 (0.0%) |
| **Student PII redacted at this layer** | 0/8 (0.0%) |

| category | cases | redacted |
|---|---:|---:|
| `span_bearer` | 4 | 4 |
| `span_bearer_uppercase` | 1 | 0 |
| `span_clean` | 16 | 0 |
| `span_credential_gap` | 3 | 0 |
| `span_event_credential` | 3 | 3 |
| `span_event_name_credential` | 1 | 1 |
| `span_jwt` | 4 | 4 |
| `span_pii_out_of_scope` | 8 | 0 |
| `span_query_token` | 6 | 6 |

**The last row of the first table is the headline of this section, and it is a zero by design.** The span exporter is a credential redactor, not a PII redactor: an email address or a phone number set as a span attribute is exported verbatim. The control on that path is that PII must never be put in a span in the first place (SPEC §5.30 - no PII in logs, traces or LLM payloads, with no exemption), verified independently by `make scan-traces` against the deployed store. Stating it as a measured 0/8 rather than as an assumption is the point of including those cases.

## 8. Findings

**No product code was changed by this experiment.** Every item below is reported, not fixed - fixing the redactor is a separate task with its own review.

### `email_exotic_syntax` - 6/8 cases disagree with the label

**F-4 (low).** Quoted local parts (`"john doe"@…`), address literals (`ada.k@[192.0.2.14]`), a double `@`, and a TLD-less host (`ada.k@localhost`) are outside `[\w.+-]+@[\w-]+\.[\w.-]+`. Unlikely from a K-12 student typing into a chat box, and listed for completeness rather than as a priority.

### `url_uppercase_scheme` - 6/6 cases disagree with the label

**F-1 (the one worth fixing).** `_URL_RE` is compiled without `re.IGNORECASE`, so `HTTP://`, `Https://` and `WWW.` are not matched at all. Scheme names are case-insensitive by RFC 3986, and a mobile keyboard's autocapitalisation produces `Https://` and `Www.` unprompted at the start of a message - which is exactly where a student pastes a link. One flag fixes it.

### `phone_parens_nospace` - 4/4 cases disagree with the label

**F-3 (low).** `\(?\d{3}\)?[-.\s]` makes the separator after the area code mandatory, so `(555)123-4567` misses while `(555) 123-4567` matches. Same digits, same grouping, one space apart.

### `neg_phone_shaped_identifier` - 8/8 cases disagree with the label

**Not a defect - the documented trade-off, priced.** These are SKUs, lot numbers and invoice numbers that genuinely carry a punctuated 3-3-4 grouping. A shape-only pattern cannot tell them from a phone number, and the module chose that direction deliberately: it redacts the phone-shaped string and keeps math content intact. The cost is bounded and visible here.

### Span-export credential gaps - 4 cases

**F-2 (medium).** Three credential shapes the span exporter's patterns do not name: `BEARER` uppercased (HTTP auth schemes are case-insensitive by RFC 7235), and `?refresh_token=` / `?id_token=` query parameters, which the *log* denylist does list as keys while the span redactor's query-parameter alternation (`token|access_token|api_key`) does not. A JWT-valued one is still caught by the JWT pattern; an opaque-valued one is not. The two layers' credential vocabularies having drifted apart is the finding, more than any single parameter name.

| case | span attribute | exported verbatim |
|---|---|---|
| `span_bearer_uppercase-001` | `http.request.header.authorization` | `BEARER abc123XYZ` |
| `span_credential_gap-001` | `auth.token_kind` | `token=abc123XYZ` |
| `span_credential_gap-002` | `auth.refresh` | `?refresh_token=abc123XYZ` |
| `span_credential_gap-003` | `auth.id` | `?id_token=abc123XYZ` |

### Over-capture (cosmetic, both directions worth knowing)

`_URL_RE`'s `\S+` runs to the next whitespace, so a URL inside JSON takes the closing quote and brace with it: `{"url": "https://example.org/x"}` redacts to `{"url": "[redacted-url]` - valid text, invalid JSON. `_EMAIL_RE`'s trailing `[\w.-]+` likewise swallows a sentence-final period. Neither leaks anything; both would matter to anything that parses a redacted payload downstream.

## 9. Limitations

1. **The regex layer detects email, URL and phone only.** Names, addresses, birth dates and student IDs are out of its contract and are governed by the structural payload-allowlist layer, which this experiment does not re-measure. No number here should be quoted as "PII detection" without that qualification.
2. **Aggregate rates depend on corpus composition.** 651 cases in chosen proportions are not a sample of production traffic; the per-category tables are the load-bearing result. No frequency or prevalence claim is made.
3. **Synthetic only.** Every value is invented. That is a deliberate constraint (no real student data may enter this repository), and it means the corpus reflects *forms* that were anticipated. A form nobody thought of is invisible here - which is exactly why the live all-positive scanners over the deployed store remain a separate, independent instrument.
4. **Local and offline.** These are pure functions and an in-memory exporter. Nothing here says what the deployed staging store contains; that is `make scan-logs` / `make scan-traces` (criterion 9) and E6.2.
5. **Layer 2's `event`-field and nested-`extra` gaps are measured on probes, not on real call sites.** The counts say what would leak if a call site did those things, not that any call site does.

## 10. Reproducing

```
uv run python benchmarks/resume_evidence/06_eval_observability/pii_probe_harness.py
uv run pytest packages/observability/tests/test_pii_probe_corpus.py -q
```

The permanent lane runs in the default `make test` collection. Its gates are set AT the values measured above (the repository's measure-first-then-gate convention) and are one-directional: recall and precision may only improve. Because the corpus is deterministic, the tolerance is exactly zero - a single newly-missed case moves the rate and fails the gate. Adding cases to the corpus therefore requires re-running this harness and updating the recorded constants deliberately, which is the intended workflow: the constants are the recorded measurement, not a threshold someone guessed.
