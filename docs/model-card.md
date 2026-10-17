# Educational correction-memory LoRA

Status at the implementation checkpoint: the bounded training path is implemented and tested with a tiny randomly initialized local model. The real pinned-Qwen optimization and adapter proof have not yet run at this source checkpoint; update this card only from saved artifacts.

This follows Task 6 of the [original folder 1 brief](superpowers/handoffs/correction-aware-memory.md), after the [drift audit](drift-audit.md). Purpose is **educational structured-rule imitation**, not a learned-memory advantage over the transparent rule, external-teacher distillation, novel memory method, or research training campaign. Actual human label reviewers remain zero.

Base: `Qwen/Qwen3-0.6B`, model and tokenizer revision `c1899de289a04d12100db370d81485cdf75e47ca`, Apache-2.0. Original synthetic train/development data: CC0-1.0, generated independently of production policy/store projection. No private records or final test data are used.

Recipe: CPU float32; seed 11; rank 16, alpha 32, dropout 0.05; `q_proj`/`v_proj` only; completion-only cross-entropy on canonical JSON plus EOS; learning rate 2e-4, three epochs, microbatch one, gradient accumulation 16, no packing and maximum total sequence 2,048 tokens. The last partial accumulation window is normalized by its actual example count. AdamW uses weight decay zero and gradient clipping at norm one. Exactly four examples per action are selected from the first eligible training observations, for twenty total.

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
