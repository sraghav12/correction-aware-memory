# First offline pilot results

Measured October 17, 2026, on Apple M4 Pro / 24 GB unified memory, Python 3.12.9. This is one seed-11 development pilot, not a locked final benchmark or trained-model result.

Dataset identity: `4d62ec91ed5c7209d325915e283fe09c5d7afcf9ab1d0976e15ef0394a763d48`.

| Outcome | Deterministic rule |
|---|---:|
| Trajectories / observations | 50 / 412 |
| Five-action macro-F1, gold-history track | 1.000 |
| State exact match, closed-loop track | 1,005 / 1,005 |
| Stale-active checkpoints | 0 / 561 |
| Missing-state checkpoints | 0 / 1,005 |
| False overwrites | 0 / 209 opportunities |
| Provenance recovered / expected | 1,358 / 1,358 |
| Invalid raw proposals, both tracks | 0 / 824 |
| Parse-invalid, gold-history / closed-loop | 0 / 412 each |
| Guard rejections | 0 |

The rule matched the independently specified synthetic oracle on this pilot. The annotations already provide candidate value, date, correction reference and source authority, so this result supports a bounded deterministic implementation, not a learned-memory contribution. The generator and rule are authored within the same project; independent code paths do not constitute independent human validation.

Human reviewers: **0**. Real model arms, trained adapters, external benchmarks, hardware resource-fit tests for a model, statistical model comparisons and a locked final holdout: **not run**. No confidence interval for a nonexistent between-arm effect is reported.

Run artifacts are generated locally under `runs/`; see the README commands to reproduce. The report includes class support, denominators, both time axes and unavailable-model labels. Saved timing/memory is single-run diagnostic process information, not an inference-serving benchmark. A poor no-op arm is tested to expose missing state; fabricated error-count fixtures independently test metric arithmetic.

Independent code review identified and reproduced three evaluator/data-integrity gaps. Regression tests now reject incomplete evidence, preserve/count closed-loop invalid outputs, and count semantic overwrites at future or historical boundaries. The original complete pilot result remains valid; the full pilot is rerun after these fixes before delivery.
