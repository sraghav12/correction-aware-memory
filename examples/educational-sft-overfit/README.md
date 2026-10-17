# One bounded accumulation adjustment

Actual CPU float32 run on October 17, 2026, from clean source `4e012c15183eb46c89c675533d8eff89574e4474`. This is the original brief's one permitted small development adjustment after [the default smoke](../educational-sft/README.md) failed its overfit criterion. **Only accumulation changed, from 16 to 1**; output directory differs too. Same seed, pinned base/tokenizer, initial adapter parameter hash, twenty-example corpus hash, three-epoch cap, rank/alpha/dropout, learning rate and token budgets. The PEFT config's target-module list order differs in serialization but denotes the same q/v module set.

| Diagnostic | Result |
|---|---:|
| Optimizer steps | 60 |
| Eval-mode mean completion loss on the same training examples | 0.675351 → 0.015978 |
| Schema-valid training outputs | 20 / 20 |
| Guard-valid training outputs | 13 / 20 |
| Parsed action labels matching target | 14 / 20 |
| Guard-valid expected-action matches | 13 / 20 |
| Exact canonical training targets | 13 / 20 |
| Full 20-example overfit criterion met | **No** |
| Base parameter hash unchanged / adapter hash changed | Yes / yes |
| Fresh-base reload token arrays identical | 2 / 2 |
| Wall time excluding initial model load | 273.234 seconds |
| Peak process memory | 7,615,758,336 bytes (7.093 GiB) |

These are **training-set diagnostics**, not held-out memory accuracy. One matching raw action label fails the guard, so only thirteen are valid action matches under the evaluator's invalid-as-wrong rule. Guard validity alone does not measure correctness; the default run's numerous wrong no-ops passed the guard more often. Two fixed development requests test serialization, not a representative evaluation. No matched prompted-base evaluation, complete closed-loop run, independent human label audit, statistical superiority, or final-test claim exists. No additional tuning followed this single adjustment.

The default failure remains preserved. This checkpoint demonstrates actual optimization, frozen base parameters, saved adapter files and reproducible loading; it does not pass the original 20/20 overfit acceptance criterion or justify scaling up.

Raw files were copied unchanged from `runs/educational-sft-overfit`. The two original LoRA checkpoint files are in `adapter/`; all original base weights remain external. Base/adapter license: Apache-2.0, included here. Code: MIT; original synthetic data: CC0-1.0. The identical training/development datasets are shared with [the default artifact](../educational-sft/dataset/). Corpus/token masks and raw outputs remain included in both artifacts.

After installing locked ML libraries and caching the base revision, choose a fresh output directory:

```bash
HF_HUB_OFFLINE=1 uv run --locked --extra ml python -m cam.cli train --config examples/educational-sft-overfit/replay-config.json --out runs/educational-sft-overfit-replayed --offline
```

`inference-config.json` points to this checkpoint and the separate development dataset; it is provided for the next controlled evaluation. That complete evaluation has not been run. `public-loader-proof.json` records the public runtime's pin/hash validation and exact replay of the two saved probes. Runtime stamps and resource measurements may vary across reproductions.
