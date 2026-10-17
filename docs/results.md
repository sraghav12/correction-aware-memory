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

Human reviewers: **0**. Complete matched model comparison arms, external benchmarks, statistical model comparisons and a locked final holdout: **not run**. Separate pretrained-runtime and educational-adapter diagnostics are recorded below. No confidence interval for a nonexistent between-arm effect is reported.

Run artifacts are generated locally under `runs/`; see the README commands to reproduce. The report includes class support, denominators, both time axes and unavailable-model labels. Saved timing/memory is single-run diagnostic process information, not an inference-serving benchmark. A poor no-op arm is tested to expose missing state; fabricated error-count fixtures independently test metric arithmetic.

Independent code review identified and reproduced three evaluator/data-integrity gaps. Regression tests now reject incomplete evidence, preserve/count closed-loop invalid outputs, and count semantic overwrites at future or historical boundaries. The original complete pilot result remains valid; the full pilot is rerun after these fixes before delivery.

## First real Qwen runtime diagnostic

The user approved downloading pinned Qwen3-0.6B weights and running ten requests. On CPU float32, the smoke finished in 28.889 seconds excluding 3.679 seconds of loading and peaked at 4.894 GiB including a passing four-token backward probe. No weights were updated and no adapter was created.

All ten outputs were valid JSON but omitted required `review_required`, yielding **0/10 schema-valid proposals**. Every raw action was `update`; each selected observation was an initial fact with expected action `create`. Several responses also contained incorrect copied source/span placeholders. Raw responses were preserved without repair, and no typed proposal reached semantic validation.

These first ten pilot observations all have empty histories and cover only initial-create events. They provide runtime and failure evidence, not a balanced five-action or closed-loop benchmark, comparison against the full rule pilot, or generalization result. The prompt and raw failures remain unchanged. The original brief's later educational SFT control is recorded below. [Complete base-smoke evidence and replay command](../examples/qwen-smoke-cpu/README.md).

## Bounded educational LoRA controls

Actual CPU float32 optimization and fresh-base reload passed for two adapters: the original default plus its one permitted accumulation adjustment. Both use the same twenty balanced training targets, seed, base and initial adapter parameter hashes, three epochs, rank/alpha/dropout, learning rate and token budgets. The default produced 19/20 schema-valid outputs, 5/20 guard-valid expected actions and 2/20 exact canonical targets. The accumulation-one adjustment produced 20/20 schema-valid outputs, 13/20 guard-valid expected actions and 13/20 canonical targets. **Neither passed the 20/20 overfit acceptance criterion.**

Same-example eval completion loss fell from .675351 to .078498 (default) and .015978 (adjustment). Full base parameters stayed unchanged, adapter parameters changed, and both saved checkpoints reproduced exact token IDs on two fixed development requests. The actual 9,189,904-byte adapter files and full corpus/loss/output/proof records are published. CPU wall time excluding initial load was 279.553/273.234 seconds; peak process memory was 6.917/7.093 GiB.

These are training diagnostics, not held-out operation accuracy or a matched prompted-base comparison. Guard acceptance alone can hide wrong abstentions; raw label match alone can hide a wrong target. Reload equality proves serialization, not memory quality. No full campaign or additional tuning followed the single adjustment. [Default evidence](../examples/educational-sft/README.md) · [Adjustment evidence](../examples/educational-sft-overfit/README.md) · [Model card](model-card.md).
