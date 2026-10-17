# Optional Qwen runtime

Status on October 17, 2026: optional runtime implemented, boundary tests exercised with injected generation, native library API check uses tiny random weights. **Pretrained Qwen smoke and backward probe are pending absent weights. Human reviewers = 0. No adapter or learned-model result exists.**

The approved [Task 5 plan](superpowers/plans/2026-10-17-correction-aware-memory.md) requires an explicit user choice before downloading absent weights. Neither selecting `qwen` nor omitting `--offline` grants download permission; both inference commands always use `local_files_only=True`. There is no automatic rule or device fallback.

## Pinned assets and dependencies

- Model/tokenizer: [Qwen/Qwen3-0.6B](https://huggingface.co/Qwen/Qwen3-0.6B), commit `c1899de289a04d12100db370d81485cdf75e47ca`, Apache-2.0. Official Hub metadata reports `model.safetensors` at 1,503,300,328 bytes, plus tokenizer/config files. No hosted inference API or cloud GPU charge is required.
- Optional extra: Torch 2.14.1, Transformers 5.20.1, Hugging Face Hub 2.2.0, transitive versions/hashes in `uv.lock`. Core commands still use the standard library.
- Baseline backend: CPU float32. An explicit copied config may select `mps`; the runtime rejects unavailable MPS rather than falling back. Actual full-model latency/memory and training feasibility are unmeasured.
- Prompt: fixed `src/cam/prompts.py`, same nonthinking/greedy settings and 2,048/256 token limits for future matched comparisons. Context overflow is a recorded failure, never truncation. At most 16 full assertion versions may be supplied.

Install libraries (no pretrained weights):

```bash
uv sync --locked --extra ml
uv run --locked --extra ml python -m pytest tests -q
```

Without the extra, the same suite skips the optional native API check. The native check uses a one-layer randomly initialized Qwen3 model and blocks network connections; it exercises generation/backward APIs on CPU and on MPS when available. This is software verification, not an experiment on the pinned pretrained model.

## Explicit cache preparation

**Run the following download only after the user explicitly chooses it.** It creates the normal external Hugging Face cache and does not put weights in Git. Budget approximately 1.5 GB for pretrained weights plus tokenizer/config files, library environment and cache overhead.

```bash
uv run --locked --extra ml python - <<'PY'
from huggingface_hub import snapshot_download
snapshot_download(
    "Qwen/Qwen3-0.6B",
    revision="c1899de289a04d12100db370d81485cdf75e47ca",
    allow_patterns=["config.json", "generation_config.json", "model.safetensors",
                    "tokenizer.json", "tokenizer_config.json", "vocab.json", "merges.txt",
                    "README.md", "LICENSE"],
)
PY
```

Cache behavior and commit pinning follow the official [Hub download guide](https://huggingface.co/docs/huggingface_hub/guides/download). Runtime loads the selected local snapshot only, uses safetensors, and disables remote custom code. The [Qwen model card](https://huggingface.co/Qwen/Qwen3-0.6B) documents nonthinking chat-template mode; greedy decoding here is a deliberate project baseline.

## Development smoke and evaluation

First use the README's offline generator if `data/generated/manifest.json` does not exist. Then:

```bash
uv run --locked --extra ml python -m cam.cli model-smoke --config configs/base.json --out runs/qwen-smoke --offline
```

This command takes the first ten requests from pilot/development data in deterministic dataset order. Earlier oracle proposals advance a separate gold-history store; gold fields never enter model prompts. Saved files include `predictions.jsonl`, `gold-history.sqlite`, `manifest.json` and `resolved-config.json`. The manifest records model/tokenizer revision, package versions, backend/dtype, load and run time, process peak memory, backward-probe outcome and source/lock identity. Each prediction preserves the request, raw decoded text, parsed proposal or failure, guard codes, latency, token counts and prompt hash. A backward failure stays explicit and permits no training claim. No optimizer or checkpoint is created. These ten requests are a runtime diagnostic, not a balanced performance study.

Only after inspecting that smoke, a full development evaluation may use:

```bash
uv run --locked --extra ml python -m cam.cli evaluate --config configs/base.json --out runs/qwen-base --offline
uv run --locked python -m cam.cli report --run runs/qwen-base --out runs/qwen-base/report --offline
```

The full evaluator retains the same gold-history and closed-loop tracks as the rules. Invalid raw outputs and guarded rejections remain errors; model performance below perfect is an experimental outcome, not a software correctness exit. Missing dependencies/cache/backend return exit 3 with no substitute results. Choose a fresh output directory for each run. The smoke command was attempted and returned exit 3 for the missing cache without creating a run directory. Pretrained inference and backward steps remain unexecuted until the cache is explicitly prepared.
