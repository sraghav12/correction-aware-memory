# Execution record

Plan: docs/superpowers/plans/2026-10-17-correction-aware-memory.md.
User authorized execution: “start working”. Branch: feature/offline-memory.

| Task | Status | Evidence |
|---|---|---|
| 1. Contracts and original fixtures | Complete | 12 tests passed; commit 40cbc0d |
| 2. Validated immutable ledger | Complete | 22 cumulative tests passed; commit 6be0375 |
| 3. Rule policy/adversarial cases | Complete | 33 cumulative tests passed; commit 64c2d40 |
| 4. Independent offline pilot/report | Complete | 49 cumulative tests passed; commit 7fe75e7 |
| 5. Prompted model runtime | Deferred | No runtime implementation/download/evaluation |
| 6. LoRA training | Deferred | No training or adapter; research gate not justified |
| 7. Learned-arm comparisons/statistics | Deferred | No learned arms or model effect |
| 8. Release A package | Review fixes verified | Canonical CLI demo; 61 cumulative tests pass; final artifact replay follows |

## Decisions made

1. Use the new independent repository on a feature branch as the isolated workspace; no second linked worktree is needed. Cost if wrong: no existing project work is exposed; this branch remains isolated.
2. Classify a repeated observation’s raw proposal as no_op(duplicate), while transaction replay returns the original committed result. Cost if wrong: duplicate raw-action labels would need revision; idempotent storage remains separately tested.
3. Stop research training at Release A because the exact annotated pilot is solved by transparent rules; actual human label review is still absent. Cost if wrong: a useful educational/model comparison is deferred, not claimed complete.

## Measured pilot

Seed 11: 50 trajectories, 412 observations, 1,005 checkpoints. Five-action macro-F1 1.000; state exact match 1,005/1,005; stale 0/561; missing 0/1,005; false overwrite 0/209. Human reviewers 0; actual model/adapter experiments 0. These are automated development-pilot results.

The detailed ignored execution ledger preserves task test commands, red/green evidence and commit ranges. No merge, push or publication has occurred.

## Independent review and fixes

Fresh review found no Critical findings and three Important findings, all reproduced before fixes:

- Incomplete/misidentified datasets could narrow denominators while passing. Eight negative variants now reject identity/count/join/group/ownership/time/coverage failures before output creation.
- Closed-loop invalid outputs were omitted from invalid-output counts and their payload was discarded. Raw outputs are retained and parse-invalid/validator-rejection denominators are explicit per track.
- False-overwrite compared only present-time views. Boundary-based semantic comparison now catches future-state mutations and historical corrections.

All 11 focused regressions failed before the fixes; the complete 61-test suite passes afterward. No Minor findings were deferred. A clean source checkout reproduced the original pilot and README commands; final fixed-code artifact replay is recorded in local manifests.

Review rulings for deliberately excluded behavior:

- Keep Qwen/LoRA/statistical comparisons deferred under the Release A gate; cost: learned-model evidence remains absent.
- Keep label review explicitly pending with zero human reviewers; cost: scientific claims remain provisional.
- Treat natural-language entailment and source-authority authentication as trusted annotation inputs; cost: this does not generalize to arbitrary extraction.
- Support the documented source-repository execution workflow; standalone installed-wheel fixture discovery is not advertised. Cost: wheel-only demo execution is not guaranteed.
- Preserve the ignored execution ledger and verification evidence rather than deleting local files; cost: a small amount of local scratch storage remains, supporting continuity and audit.
