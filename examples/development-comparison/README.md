# Matched exploratory development evidence

Measured October 17, 2026. Five frozen development trajectories, 44 observations, 103 checkpoints, 88 separate calls per arm. Actual inference source: `adede561089be63b0cab064d46440174a28d6505`, clean for every arm.

[Readable Markdown outcomes and intervals](comparison.md) · [Readable HTML viewer](viewer.html) · [All metrics/per-trajectory counts](comparison.json) · [Registration written before inference](registration.json) · [Failure categories](failure-summary.json)

Each arm directory retains original byte-for-byte requests/raw responses, model metadata, guard/commit results, checkpoints, rate numerators and denominators, per-trajectory metrics, independent SQLite stores, resolved config, label-audit packet and HTML trace. These are original synthetic annotations, not private user records. Dataset text is CC0-1.0; code is MIT; pinned base and adapter licenses are documented in the model card.

## Replay

Requires the cached pinned model and locked ML extra. From the repository root, choose a fresh output directory:

```bash
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run --locked --extra ml cam compare \
  --config examples/development-comparison/replay-config.json \
  --out runs/development-comparison-replay --offline
```

The bundled arm configs resolve the already committed development data and two adapter checkpoints. Original resolved configs preserve their actual local paths; source identity and hashes remain unchanged. Timing is machine dependent. The original model responses are not repaired or regenerated in this package.

## Interpretation

Zero human label reviewers. One distinct training seed11, two configurations. Two development reload probes had been seen before registration; this is exploratory development, not a blinded final evaluation. Both adapters failed the twenty-target overfit check. The final test/full research splits, style transfer, independent seed variation and research training controls remain unexecuted.

For stale-rate differences, negative is favorable only with missing-state and false-overwrite non-regression. Intervals resample five whole paired trajectories and pool counts over 2,000 draws; undefined zero-denominator draws remain counted. These conditional intervals do not demonstrate external generalization or training-seed robustness. Latest-arrival is a weak diagnostic with all production guards retained.

Per-call end-to-end latency means the proposer wrapper, including prompt preparation, tokenization, generation and parsing; it excludes Store snapshot/commit and scoring. Model-only measures runtime generation plus decoding. Whole-arm wall time includes the replay/evaluation work; model load is separate. Peak memory is the process lifetime high-water mark and can include earlier arms. P95 uses the recorded empirical rank `max(0, floor(0.95*n)-1)`; the complete call times are retained.

[Prospective decisions and remaining scope](../../docs/development-comparison.md) · [Original brief alignment](../../docs/drift-audit.md).

The readable viewer is regenerated from saved results after the run; original `index.html` and all59 runtime files remain unchanged. No model was called to create it.
