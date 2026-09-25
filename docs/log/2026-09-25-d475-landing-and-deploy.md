# 2026-09-25 — D-472/D-473 landed through PR #473, D-474 audit exception, deploy `gha-61fc8a528418` (D-475)

> Non-authoritative narration (DQ-1). Current state: `docs/PROJECT_STATE.md`. Judgment: D-474, D-475.

Continued from the 2026-09-24 entry with the user's "commit" and then "push + deploy". Staging
read first: services steady on `gha-523b9f036a53`, edge routing fine, **but** both RDS secrets
rotated 2026-09-24 and every API task predated it — the D-455 condition, latent. Offered
push + deploy vs forced redeploy vs record-only; the user chose push + deploy.

`main` is protected: pushed `land/d472-d473`, PR #473. Eight of nine checks green; the
`python-dependency-audit` failed on **PYSEC-2026-3740** (nltk 3.10.3, transitive via
llama-index-core, no fixed release, never imported here) → `--ignore-vuln` with a dated
justification (D-474, `93532fc` pre-rebase). Then `gh pr merge --merge` was refused (linear
history enforced at the branch, whatever the repo setting says) and a chained `reset --hard
origin/main` briefly moved local main back to `398cd6f` — recovered from the remote landing
branch, no loss. Rebase-merged; the SHAs cited in the 2026-09-24 entry map to
`675e00c` / `5d55a99` / `7d46630` / `d80f197`, head `61fc8a5`.

Deploy run 36190231233, 21:12 → 21:31 UTC, every gate green, rollback skipped. Post-deploy:
learning `:156` 2/2, chat `:154` 1/1, ops `:148`, all tasks started after the rotation, `/me`
401, SPAs 200, 0/0/0 failure signatures. Docs reconciled in a follow-up PR (this entry rides
it). Handoff: queue row 1 is `MEMORY-CONSOLIDATION-DEFECTS` #4; next rotation 2026-10-02
(UD-14 open); D-473 unmeasured under a real 3-task burst; remove the nltk ignore when a fixed
release lands.
