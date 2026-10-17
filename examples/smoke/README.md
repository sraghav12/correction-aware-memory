# Committed synthetic smoke run

Two pilot trajectories, original synthetic inputs only. Full raw predictions/checkpoints, SQLite ledgers, metrics, audit sample and HTML report are included. No model inference/training or human label validation occurred. The run manifest identifies the exact clean source commit used.

Only absolute output/data paths in resolved-config.json were normalized to relative paths for portability; raw evidence, dataset hashes and measured metrics are unchanged. From the repository root:

```bash
uv run python -m cam.cli evaluate --config examples/smoke/replay-config.json --out runs/smoke-replayed --offline
uv run python -m cam.cli report --run runs/smoke-replayed --out runs/smoke-replayed/report --offline
```

Use fresh output directories. Runtime stamps, latency and process-memory measurements may differ; projected states and data identity must match.
