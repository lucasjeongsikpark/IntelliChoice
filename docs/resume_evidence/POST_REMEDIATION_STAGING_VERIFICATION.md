# Post-Remediation Staging Verification

> Written 2026-08-30 after the deploy of `523b9f0` (image `gha-523b9f036a53`, run 33296426748)
> and the R5 targeted smoke verification. Raw evidence: `staging_verification/` (this directory);
> the R5 check register is `staging_verification/R5_STAGING_SMOKE_SUMMARY.md` (34 checks).
> Historical benchmark artifacts are untouched; this document ADDS the staging layer.
>
> **Environment vocabulary, used exactly:** *large benchmark evidence* = the nine-experiment
> program (D-458..D-465); *local remediation verification* = the R1–R4 fix-time measurements;
> *staging smoke verification* = R5 on the deployed image; *real-model* = actual Bedrock calls;
> *simulated/load-test* = synthetic traffic, never real users.

**Deployed revisions (before → after, read from the ECS API, not CI):**
learning-api `:154` → **`:155`** (2/2 running), chat-api `:152` → **`:153`** (1/1 running),
ops-task → `:147`; image `gha-5fa15d491057` → **`gha-523b9f036a53`** (= main `523b9f0`,
D-467..D-470 + the nltk PYSEC-2026-3726 fix). Rollout COMPLETED on all services; deploy
workflow gates all green (deployed-version, canary bake, image-consistency, SPA syncs +
invalidations, CloudFront smoke). R5 total Bedrock spend: **15.25¢**.

## Claim table

| Claim | Original measurement | Remediation | Staging verification | Environment | Safe resume wording | Important limitation |
|---|---|---|---|---|---|---|
| Memory consolidation fails closed; no silent-zero runs | E4: 29/30 real calls truncated → `{}` validated as empty → 0 facts, exit 0 (silent) | D-467: stop-reason check before validation; budget 1280→2560; local real re-run: facts 6→119 at 119/119 provenance, 11 reported failures | **8/8 truncated calls ALL surfaced** (`bedrock_call_failed` + named ceiling each), **0 silent** (zero successful call records = the shape cannot exist), job exited non-zero and the failure alarm legitimately paged | staging smoke, real-model (13.40¢) | "Found a silent LLM-consolidation failure via real-model evaluation, fixed it fail-closed, re-validated 119 facts at 100% provenance" | Truncation itself is NOT eliminated — the staging fixture cohort (load-test-bloated, ~26 facts) still saturates the 4000-token hard cap (`MEMORY-CEILING-STILL-SATURATED`, reported). "Consolidation produces facts" evidence is the LOCAL n=10 re-run, not this staging probe (which wrote 0 facts, honestly) |
| Unhandled 500s are observable and alertable | D-455: 114 tracebacks invisible to every ERROR filter/alarm | D-468: JSON `level=ERROR` line (failing test → 5 permanent tests); staging `Traceback` filter + alarm | Filter counted a synthetic traceback (1.0, and correctly **excluded** a real JSON `unhandled_exception` line — counted 1 not 2); alarm OK→ALARM 06:52:07Z with actions disabled, self-resolved 07:07:30Z; **0/40 alarms left with actions disabled**. App-side line: **no safe unhandled-500 trigger exists** (0/16 probes) — verified by deployed-image consistency + the 5 permanent tests instead | staging smoke ($0) + local tests | "Made unhandled failures observable: structured redacted ERROR events plus a log-pattern alarm proven end-to-end without paging" | The app-side JSON line was never fired by a real staging 500 (no safe trigger — itself decent news); its proof is code-presence + permanent tests |
| Telemetry export is watched | AUD-F-12: collector silently dropped 100% of spans, nothing noticed; E6.2: counters unscraped | D-468: `:8888` scraped, 4 counters promoted + failure alarms | Fresh post-deploy datapoints (19 × 8 series), failures 0, 4/4 alarms enabled | staging smoke ($0) | "Closed a silent telemetry-export blind spot with scraped exporter counters and failure alarms" | Informational-severity alarms; one build/day of datapoints |
| The content gate detects mismatched hints and arithmetic clones | E5.2: hint class 0/17 on every detector; near-dup 8/17; pipeline F1 0.837 | D-469: deterministic hint-coherence check + fingerprint in dedup; 12/17 at 0 FP (incl. 0/958 bank), 17/17, F1 0.949 | Deployed image is 523b9f0's build; permanent lanes **146/146** green (10+16+27+93); frozen D-469 numbers restated, not re-measured | large benchmark (frozen denominators) + local lanes; staging = code-presence | "Cut pipeline defect-detection misses by half: F1 0.837→0.949 on a frozen 6-class corpus, zero false positives incl. all 958 approved items" | The gate is offline tooling — "deployed" means the image carries it; E5.3's skeleton-collision residual is measured open |
| PII redaction at measured precision/recall | E6.1: precision 97.0 / recall 94.2 (F-1/F-2 gaps found) | D-470: IGNORECASE + reconciled credential vocabulary; recall 96.4%, F1 96.7%, URL 74/74, 0 new FPs | Frozen corpus re-run on the landed implementation: **byte-identical to R4's post-fix CSV**; lane 54/54 | local ($0, the corpus is offline by design); staging = code-presence via image consistency | "Measured the PII redaction layer at 97.1% precision / 96.4% recall over 651 labeled probes, then fixed and re-measured its two worst gaps" | Regex-layer scope is email/URL/phone (names are the structural allowlist layer's job); F-3/F-4 remain as priced trade-offs |
| Deployed platform health after the remediation deploy | D-456/E1: load ceilings + 22.36 req/s sustained | (no change intended) | ALB 5xx 0 vs 0 baseline; 4xx = 6, all this task's own probes; RDS connections avg 16.3/max 20 (24 h max 62); one guest chat turn 200/14.6 s/1 citation; authenticated learning reads 200 | staging smoke (1.85¢ chat turn) | (supports the platform bullets; not itself a bullet) | Point-in-time health, not a load run |

## What R5 additionally surfaced (reported, not fixed)

- **`MEMORY-CEILING-STILL-SATURATED`** — at ~26 existing facts the derived output budget is 5,888
  tokens, hard-capped to 4,000; past `MAX_SAFE_EXISTING_FACTS=11` no ceiling helps. Material
  caveat: the probe's 7-day window includes this week's load-test traffic (13,872 events dropped
  vs 0 on the 2026-08-23 run), so the cohort is pathological relative to a real student week.
  The fix direction (bounding the response shape / which-facts-to-drop) is the open design
  decision D-467 already named — now with live evidence attached.
- **One true-positive page**: the probe's all-calls-failed exit-1 legitimately fired the ops-task
  failure alarm (the AUD-F-34 alarm doing exactly its job) — a real SNS page was sent.
- **Ops-task logging gap** (minor): the gateway's structured log extras are unrendered in the
  ops-task log configuration.
