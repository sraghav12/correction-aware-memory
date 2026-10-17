# Methods and experiment decisions

## Implemented experiment

One scalar predicate (`release_state`) and values `preliminary`, `published`, `withdrawn`, or explicit null. Exact entity matching; trusted loader annotations for value, authority, effective date and correction authorization. All five action proposals use the same deterministic validator and immutable SQLite transaction path.

Two separate passes answer distinct questions. Gold-history action classification gives each proposer the same correct historical snapshot and evaluates raw five-action macro-F1. Closed-loop replay starts an independent empty ledger and measures its own accumulated state against fixed independently specified checkpoints. A recovery operation in a diverged store is not scored against an incompatible gold-history action label.

State exact match includes value, retraction/absence status, effective boundary and interval end. Provenance is separately scored with source-set precision/recall; mechanical source/span validation is separate from entailment. Stale-active rate uses changed gold checkpoints and explicitly excludes absent selections; missing-state rate is reported beside it. False-overwrite follows the handoff's literal operational definition: semantic changes at gold non-mutating opportunities / all such opportunities. This metric can include recovery from a prior model error; interpret it with state exact match and missing-state rate when model arms are introduced. Deterministic QA checks the same key/time answer and source set; it is not evidence from an independent language-answer task.

Invalid raw proposals count as errors. Conservative no-op is not silently made correct. Undefined rates use null and denominator zero. Per-trajectory records and every raw request/proposal/commit/checkpoint are saved. Runtime stamps and measured latency can differ across replay; source, dataset and projected-state hashes must reproduce.

## Training gate

**Decision: `training_not_justified` for a research training campaign in this bounded annotated-input MVP.** The first automated pilot matches all 412 operation labels and 1,005 state checkpoints using transparent rules. This is provisional automated evidence: human reviewers = 0. It does not certify independent label quality or imply that arbitrary language memory is solved.

Tasks 5–7's prompted-model runtime, LoRA training, learned-arm ablations and paired inference comparison are deferred under the design's explicit Release A stop condition. No weights were downloaded, no ML dependencies installed, no adapter trained, and no final holdout opened. CLI requests for these unavailable phases return exit 3 rather than rule substitutes or tracebacks. Revisit after the pilot audit: a tiny SFT experiment may demonstrate rule imitation; a learned-memory contribution needs a separately justified task. Do not weaken the rule or change test difficulty after seeing results to obtain a model win.

## Uncertainty and limitations

One development generator seed (11), no human-reviewed labels, no independently written style set, no external benchmark, and no model arms. No between-model effect, confidence interval or statistical significance is claimed. Full model experiments would use frozen splits, matched revisions/budgets, seeds 11/22/33 where feasible, and 2,000 paired whole-trajectory bootstrap draws with pooled numerators/denominators. Those experiments have not run.

Resource timings are a single process run on this Mac; process memory can include prior work and warmup is not isolated. They are diagnostic, not serving benchmarks or CUDA evidence. Annotation-determined actions and a tiny predicate vocabulary sharply limit generalization.
