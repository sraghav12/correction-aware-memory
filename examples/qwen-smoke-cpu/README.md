# First pretrained Qwen smoke: CPU

Measured October 17, 2026, on Apple M4 Pro / 24 GB, using clean source commit `c655119f46d3f462393c6f5af0ab4cbb346ade5a`. Qwen3-0.6B model/tokenizer revision `c1899de289a04d12100db370d81485cdf75e47ca`, CPU float32, nonthinking greedy decoding, input/output budgets 2,048/256 tokens. The user explicitly authorized the download and ten local requests. Weights stay outside Git.

**The runtime worked; the base model failed the proposal schema on all ten requests.** Every response was syntactically valid JSON but omitted required `review_required`. All emitted raw action `update` for initial facts whose expected operation was `create`; several also copied incorrect provenance/span placeholders. No response was repaired. No typed proposal reached the shared guard. The SQLite file here contains **oracle gold-history commits only**, not accepted model decisions.

| Diagnostic | Measured |
|---|---:|
| Requests | 10 |
| Syntactically valid JSON objects | 10 / 10 |
| Schema-valid proposals | 0 / 10 |
| Missing `review_required` | 10 / 10 |
| Semantic guard evaluations | 0 |
| Input / output tokens | 7,047 / 787 |
| Median proposer latency | 2.560 seconds |
| Total proposer latency | 26.990 seconds |
| Model load | 3.679 seconds |
| Smoke wall time, excluding load | 28.889 seconds |
| Peak process memory, including backward probe | 5,254,381,568 bytes (4.894 GiB) |
| Four-token backward probe | Passed; finite gradients, 1.728 seconds |
| Weight updates / adapter | None |

Selection is the first ten observations in deterministic pilot order. **All ten are initial `create` events with empty histories**, from different trajectories. This is a narrow runtime diagnostic, not a balanced five-action test, closed-loop evaluation, generalization claim, prompt-selection holdout, serving benchmark, or comparison against the full 412-observation rule run. A four-token backward pass proves basic compatibility only, not full LoRA memory fit or training feasibility. Human reviewers remain zero. No training or prompt tuning followed this result.

Raw requests, exact decoded responses, parse errors, prompt hashes, token counts and timings are in `predictions.jsonl`. `manifest.json` and `resolved-config.json` are byte-for-byte run records; the latter retains the original local data path. `summary.json` derives counts from these records. `assets.json` records downloaded-file checksums, and `artifact-sha256.json` binds the eight evidence/config files. `console.log` includes the CLI result. Model weight SHA-256: `f47f71177f32bcd101b7573ec9171e6a57f4f4d31148d38e382306f42996874b`.

To reproduce, install the locked ML extra and explicitly cache the complete pinned snapshot as described in [model setup](../../docs/model-runtime.md). Generate the original pilot using the root README if needed, then choose a fresh output directory:

```bash
HF_HUB_OFFLINE=1 uv run --locked --extra ml python -m cam.cli model-smoke --config examples/qwen-smoke-cpu/replay-config.json --out runs/qwen-smoke-replayed --offline
```

The portable replay config changes only the data path from the base config. Runtime stamps/resources may differ. Inspect actual new raw responses rather than assuming this diagnostic generalizes.
