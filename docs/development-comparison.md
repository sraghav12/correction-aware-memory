# Prospective exploratory development comparison

Registered before this comparison's inference on October 17, 2026. This is **development**, not a blinded preregistered final study: two development requests have already appeared in the adapter reload probes. No new training, checkpoint selection, prompt adjustment or decoding sweep follows these results.

The existing frozen development dataset has five trajectories and 44 observations, identity `3bbd47549bba3ce17bfc8fa741ba3fc906daa9de065d69529ab879bfd6346996`. Its complete files are already committed under `examples/educational-sft/dataset/development/`. The original 600/100/150 research split and style-transfer study remain unexecuted; final tests stay unopened. Both educational adapters failed the twenty-target overfit acceptance check, and actual human label reviewers remain zero.

Arms, in fixed execution order:

1. Conservative rule proposer.
2. Prompted pinned Qwen3-0.6B base, the statistical reference.
3. Default educational adapter (accumulation16).
4. Single permitted adjusted educational adapter (accumulation1).
5. Weak latest-arrival heuristic, visibly diagnostic and still subject to the same production guard. It follows the most recently supported version, ignores correction semantics, and often proposes writes the guard rejects. This is not a guard-removal ablation.

All arms use the same content-hashed observations and gold-history snapshots, the same shared guard and immutable Store implementation, and fresh separate stores. Closed-loop requests may diverge because each arm accumulates its own errors. Every observation is called separately in both tracks; no shared-response cache hides inference costs. Main model arms use CPU float32, identical pinned model/tokenizer revision, the unchanged prompt, greedy nonthinking unconstrained decoding, 2,048 input and 256 generated token caps, and strict parse/reject with no repair. Overflow remains an observed failure. No warmup calls are excluded. Model load, each track's generation/proposer-wrapper latency and tokens, and process lifetime peak memory are reported separately; proposer-wrapper latency excludes Store snapshot/commit and scoring; the latter includes earlier arms and is not an isolated per-arm allocation estimate.

Primary endpoint: pooled stale-active-rate difference, arm minus prompted base. Lower stale rate is favorable only with non-regression in missing-state and false-overwrite rates; no-op systems cannot earn a safety claim from missing everything. All other rates, state/QA/provenance, raw action F1 and guard-valid action F1 are secondary. Raw action F1 retains a parsed action even when its proposal fails the guard; malformed outputs count as wrong. Guard rejection is separately reported. Erroneous mutations among commits count committed semantic timeline changes whose resulting timeline differs from current gold history, divided by all committed proposals, including reinforcement/no-op; successful recovery is not itself an erroneous mutation. This differs from false overwrite's denominator of gold non-mutating opportunities.

For every rate, resample paired **whole trajectories** 2,000 times with seed11, pool each arm's numerators and denominators within a draw, and compute arm-minus-base rate differences. Report 95% percentile intervals with linear interpolation, the observed pooled contrast, and undefined zero-denominator draw counts. Five trajectories give fragile, conditional intervals; they do not measure training-seed variation or population generalization. Actual distinct adapter-training seeds = one (11); both configurations remain separate arms. One greedy inference run per arm, no artificial seed/event pooling.

Equal-token/no-correction research training controls, guard-removal sandbox, larger model, constrained-decoding pairing, final-test study and actual independent human audit remain deferred. No correction-focused research advantage or learned-memory superiority is claimed.

Replay with cached weights and the locked optional environment:

```bash
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run --locked --extra ml cam compare \
  --config configs/comparison-development/comparison.json \
  --out runs/development-comparison --offline
```

The output directory must be fresh. The runner writes `registration.json` before starting an arm, including resolved configs, dataset identity, code/lock/prompt identity and limitations. It writes raw completed calls incrementally; an unavailable backend remains an unscored unavailable arm. Completed arms retain all raw proposals, checkpoints, metrics, per-trajectory counts, stores and inspection reports. `comparison.json`, `comparison.md` and `index.html` contain the paired summaries.
