# Educational correction-memory LoRA

Status: two actual bounded educational LoRA runs trained, saved and reloaded adapters with unchanged base weights. The [default](../examples/educational-sft/README.md) matched 2/20 canonical training targets; the one permitted [accumulation adjustment](../examples/educational-sft-overfit/README.md) matched 13/20. **Both failed the full 20/20 overfit acceptance criterion.** No larger campaign or further tuning followed.

This follows Task 6 of the [original folder 1 brief](superpowers/handoffs/correction-aware-memory.md), after the [drift audit](drift-audit.md). Purpose is **educational structured-rule imitation**, not a learned-memory advantage over the transparent rule, external-teacher distillation, novel memory method, or research training campaign. Actual human label reviewers remain zero.

Base: `Qwen/Qwen3-0.6B`, model and tokenizer revision `c1899de289a04d12100db370d81485cdf75e47ca`, Apache-2.0. Adapter artifacts are also Apache-2.0, with the base license included; code is MIT. Original synthetic train/development data: CC0-1.0, generated independently of production policy/store projection. No private records or final test data are used.

Recipe: CPU float32; seed 11; rank 16, alpha 32, dropout 0.05; `q_proj`/`v_proj` only; completion-only cross-entropy on canonical JSON plus EOS; learning rate 2e-4, three epochs, microbatch one, gradient accumulation 16, no packing and maximum total sequence 2,048 tokens. The last partial accumulation window is normalized by its actual example count. AdamW uses weight decay zero and gradient clipping at norm one. Exactly four examples per action are selected from the first eligible training observations, for twenty total.

The default made six optimizer steps. The original brief permits one small development adjustment: `configs/sft-overfit.json` changes only accumulation to one, making sixty steps. Corpus, initial adapter and base parameter hashes match across runs. Full masks/prefixes contain actual tokenizer IDs; initial data preflight caught the library's dictionary-return default before any optimization, and explicit `return_dict=False` plus prefix-identity checks corrected it.

| Training diagnostic | Default: accumulation 16 | Adjustment: accumulation 1 |
|---|---:|---:|
| Same-example eval completion loss | 0.675351 → 0.078498 | 0.675351 → 0.015978 |
| Strict schema-valid outputs | 19/20 | 20/20 |
| Guard-valid expected-action matches | 5/20 | 13/20 |
| Exact canonical targets | 2/20 | 13/20 |
| Overfit achieved | No | No |
| Frozen base / changed adapter verified | Yes | Yes |
| Fresh-base reload token arrays identical | 2/2 | 2/2 |
| CPU wall seconds excluding initial load | 279.553 | 273.234 |
| Peak process memory, GiB | 6.917 | 7.093 |

Each adapter trains 2,293,760 of 598,343,680 parameters and occupies 9,189,904 safetensors bytes. The two fixed development requests only verify reload identity; they do not measure generalization. The default responses are themselves poor (one extra `text` field and a wrong no-op). Guard validity is not semantic accuracy. These twenty-item training diagnostics must not be compared numerically to the earlier ten-item initial-create base smoke as a matched result.

Measured optimization averaged about 2.5–2.8 seconds per microbatch on this Mac. A rough extrapolation for 600 trajectories of 6–10 events, three epochs, is approximately 8–14 CPU hours for optimization alone, excluding evaluation and other overhead. This is an unexecuted estimate; actual sequence lengths and implementation/hardware matter. No such campaign is justified or scheduled.

Prompt tokens are all masked with `-100`, and actual prefix token IDs must exactly match the inference template. Real-tokenizer preflight verifies complete integer token IDs and rejects overlength examples rather than truncating. Full base-parameter hashes before/after optimization and changed adapter hashes are required. Checkpoint loading verifies base/tokenizer revision, saved file hashes and successful reload proof. Greedy generation settings match the base smoke.

The final bounded checkpoint is saved without research checkpoint selection. Two fixed development requests (initial create and authorized correction) must reproduce exact generated token IDs after reload onto a fresh pinned base. Twenty post-training greedy requests measure exact canonical target reproduction and schema validity. A failure to overfit within the cap remains a recorded failure; it does not authorize a sweep or larger campaign.

Reproduce using fresh output directories:

```bash
uv sync --locked --extra ml
uv run --locked --extra ml python -m cam.cli generate --config configs/sft.json --out data/generated/sft-train --offline
uv run --locked --extra ml python -m cam.cli generate --config configs/development.json --out data/generated/sft-development --offline
HF_HUB_OFFLINE=1 uv run --locked --extra ml python -m cam.cli train --config configs/sft.json --out runs/educational-sft --offline
```

Training requires the already cached complete pinned base snapshot. No automatic download or paid fallback is used. Optional dependencies remain outside the offline core. The implementation uses [PEFT LoRA](https://huggingface.co/docs/peft/en/package_reference/lora) with a small explicit PyTorch loop so masking, sequence bounds and accumulation behavior are visible. Research development selection, frozen full comparison splits, manual audits and trajectory uncertainty remain separate milestones.

For direct replay from the committed dataset/corpus package, use either artifact's `replay-config.json` and a fresh `--out`. For inference, keep `manifest.json` beside the `adapter/` directory; the public loader verifies base/tokenizer pins, successful training/reload proof and both checkpoint file hashes. Actual production sources were clean `06c159e` and `4e012c1`, respectively. After the default run, saving was made explicitly embedding-free to prevent PEFT's automatic remote config check; this changed save-time network behavior, not training math or the recorded default adapter. Both actual runs used `HF_HUB_OFFLINE=1`.

## Exploratory matched development evidence

| Arm | Raw action F1 | Guard-valid F1 | State exact | Stale | Missing |
|---|---:|---:|---:|---:|---:|
| base | 0.050 | 0.000 | 0/103 | 0/38 | 103/103 |
| latest-arrival | 0.662 | 0.723 | 91/103 | 12/38 | 0/103 |
| rule | 1.000 | 1.000 | 103/103 | 0/38 | 0/103 |
| sft-adjusted | 0.474 | 0.513 | 75/103 | 15/38 | 0/103 |
| sft-default | 0.261 | 0.277 | 14/103 | 0/38 | 87/103 |

[Full results and paired intervals](../examples/development-comparison/README.md) use five trajectories,44 observations,88 calls per arm and one training seed. This separates training-target reproduction from the adapters’ behavior on unseen synthetic development trajectories; two development reload probes had already been inspected. No additional tuning or full-study/generalization claim followed.
