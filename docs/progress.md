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
| 8. Release A package | In final review | Canonical CLI demo; 50 cumulative tests pass |

## Decisions made

1. Use the new independent repository on a feature branch as the isolated workspace; no second linked worktree is needed. Cost if wrong: no existing project work is exposed; this branch remains isolated.
2. Classify a repeated observation’s raw proposal as no_op(duplicate), while transaction replay returns the original committed result. Cost if wrong: duplicate raw-action labels would need revision; idempotent storage remains separately tested.
3. Stop research training at Release A because the exact annotated pilot is solved by transparent rules; actual human label review is still absent. Cost if wrong: a useful educational/model comparison is deferred, not claimed complete.

## Measured pilot

Seed 11: 50 trajectories, 412 observations, 1,005 checkpoints. Five-action macro-F1 1.000; state exact match 1,005/1,005; stale 0/561; missing 0/1,005; false overwrite 0/209. Human reviewers 0; actual model/adapter experiments 0. These are automated development-pilot results.

The detailed ignored execution ledger preserves task test commands, red/green evidence and commit ranges. No merge, push or publication has occurred.
