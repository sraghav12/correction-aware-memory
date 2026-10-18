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

Human reviewers: **0**. At the first rule-only milestone, no between-model comparison had run. The later bounded development comparison is recorded below; external benchmarks and a locked final study remain unexecuted.

Run artifacts are generated locally under `runs/`; see the README commands to reproduce. The report includes class support, denominators, both time axes and unavailable-model labels. Saved timing/memory is single-run diagnostic process information, not an inference-serving benchmark. A poor no-op arm is tested to expose missing state; fabricated error-count fixtures independently test metric arithmetic.

Independent code review identified and reproduced three evaluator/data-integrity gaps. Regression tests now reject incomplete evidence, preserve/count closed-loop invalid outputs, and count semantic overwrites at future or historical boundaries. The original complete pilot result remains valid; the full pilot is rerun after these fixes before delivery.

## First real Qwen runtime diagnostic

The user approved downloading pinned Qwen3-0.6B weights and running ten requests. On CPU float32, the smoke finished in 28.889 seconds excluding 3.679 seconds of loading and peaked at 4.894 GiB including a passing four-token backward probe. No weights were updated and no adapter was created.

All ten outputs were valid JSON but omitted required `review_required`, yielding **0/10 schema-valid proposals**. Every raw action was `update`; each selected observation was an initial fact with expected action `create`. Several responses also contained incorrect copied source/span placeholders. Raw responses were preserved without repair, and no typed proposal reached semantic validation.

These first ten pilot observations all have empty histories and cover only initial-create events. They provide runtime and failure evidence, not a balanced five-action or closed-loop benchmark, comparison against the full rule pilot, or generalization result. The prompt and raw failures remain unchanged. The original brief's later educational SFT control is recorded below. [Complete base-smoke evidence and replay command](../examples/qwen-smoke-cpu/README.md).

## Bounded educational LoRA controls

Actual CPU float32 optimization and fresh-base reload passed for two adapters: the original default plus its one permitted accumulation adjustment. Both use the same twenty balanced training targets, seed, base and initial adapter parameter hashes, three epochs, rank/alpha/dropout, learning rate and token budgets. The default produced 19/20 schema-valid outputs, 5/20 guard-valid expected actions and 2/20 exact canonical targets. The accumulation-one adjustment produced 20/20 schema-valid outputs, 13/20 guard-valid expected actions and 13/20 canonical targets. **Neither passed the 20/20 overfit acceptance criterion.**

Same-example eval completion loss fell from .675351 to .078498 (default) and .015978 (adjustment). Full base parameters stayed unchanged, adapter parameters changed, and both saved checkpoints reproduced exact token IDs on two fixed development requests. The actual 9,189,904-byte adapter files and full corpus/loss/output/proof records are published. CPU wall time excluding initial load was 279.553/273.234 seconds; peak process memory was 6.917/7.093 GiB.

These training diagnostics are separate from the matched development replay below. Guard acceptance alone can hide wrong abstentions; raw label match alone can hide a wrong target. Reload equality proves serialization, not memory quality. No full campaign or additional tuning followed the single adjustment. [Default evidence](../examples/educational-sft/README.md) · [Adjustment evidence](../examples/educational-sft-overfit/README.md) · [Model card](model-card.md).

## Matched exploratory development comparison

All five arms completed on the same five development trajectories, 44 observations and two separate scoring passes (88 calls per arm). Original full research splits, style transfer and final evaluation remain unexecuted. CPU float32 and identical pinned model/tokenizer, unchanged prompt, 2,048/256 token budgets and greedy strict parse/reject apply to all three model arms. The rule and weak latest-arrival diagnostic use the same guard; each arm starts fresh independent stores.

| Arm | Raw action F1 | Guard-valid F1 | State exact | Stale | Missing |
|---|---:|---:|---:|---:|---:|
| base | 0.050 | 0.000 | 0/103 | 0/38 | 103/103 |
| latest-arrival | 0.662 | 0.723 | 91/103 | 12/38 | 0/103 |
| rule | 1.000 | 1.000 | 103/103 | 0/38 | 0/103 |
| sft-adjusted | 0.474 | 0.513 | 75/103 | 15/38 | 0/103 |
| sft-default | 0.261 | 0.277 | 14/103 | 0/38 | 87/103 |

Raw action F1 scores parsed labels before semantic guards; guard-valid F1 additionally rejects invalid targets/evidence/actions. Schema-invalid outputs count as incorrect in both. The earlier rule-only result is unaffected by this distinction. Zero stale state with high missing state cannot support a safety claim.

Primary contrast is pooled stale rate, arm minus prompted base, with missing-state and false-overwrite constraints. The saved report includes all rate contrasts, 95% paired whole-trajectory percentile intervals, supports/denominators and zero-denominator draw counts (2,000 resamples, seed11). These intervals condition on five synthetic development trajectories, not independent training runs or external generalization. Actual distinct adapter training seeds = one; two development probes were previously inspected. No checkpoint selection, prompt changes, additional training or final-test access followed this comparison.

[Full comparison, intervals and replay evidence](../examples/development-comparison/README.md) · [Prospective settings and definitions](development-comparison.md). At that experiment milestone, human label reviewers were zero; both adapters still fail the twenty-target overfit requirement. The full controlled research study remains unfinished.

In the adjusted adapter, exact deterministic value-plus-source QA matched 29/103 checkpoints, versus 75/103 for semantic state alone. Missing provenance support remains a separate failure. Its stale-rate contrast against the empty base was +15/38 (95% conditional interval [0.0, 0.9]); 19 of 2,000 draws had zero changed-checkpoint denominator and remain explicitly undefined. This is no primary stale-rate improvement.

## Subsequent separate AI label review

At the user's request, the existing 50-event pilot packet (114 queries) received a blinded API cross-check: expected actions/states were hidden, while trusted observations, gold histories and query schedules were supplied. Gemini 2.5 Flash Lite via OpenRouter completed all 50 requests, matching 39 action labels, 32 complete proposals and 67/114 complete state/provenance queries; 20 cases matched entirely. A separate AI adjudication inspected all 30 differing cases against the written contract and established no gold-label defect; the differences were reviewer-model errors. This is AI consistency evidence, not independent human validation.

The initial Haiku 5.5 attempt and blocked follow-up are retained, including 31 token-exhausted answers and credit errors; none were silently replaced. [Complete evidence, scope, costs and offline verification](../examples/ai-label-review/README.md). Current human progress is one participant/one accepted case in a separate local working copy. Earlier reviewer counts above describe the original experiment milestones; the full human audit and final study remain incomplete. No original model result or gold label changed.
