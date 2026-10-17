# Correction-Aware Small-Model Memory: Design and Implementation Plan

> **For agentic workers:** Implement the checklist task by task. If available, use `superpowers:executing-plans`; `superpowers:subagent-driven-development` is an optional alternative when the user authorizes delegation. Otherwise execute normally, verifying each task before proceeding. This document contains the complete embedded design; no sibling document or proprietary tool is required.

**Goal:** Build and evaluate a small model that proposes safe, evidence-grounded memory changes when facts are repeated, corrected, or superseded.

**Architecture:** A deterministic ingestion envelope supplies one atomic observation, matching memory, trusted metadata, and evidence. A rule or language model proposes one structured action; a shared transaction validator commits immutable events and derives temporal views. Compare a deterministic baseline, prompted Qwen3, and a LoRA adapter through the same evaluator.

**Tech stack:** Proposed Python 3.11+, standard-library SQLite/JSON/hash tooling, pytest; optional PyTorch, Transformers, PEFT, TRL, and Datasets for model work. These are provisional choices: verify current compatible releases and pin the actual working versions before installation. No dependencies are installed by this plan.

**Spec:** Embedded sections below, from “Purpose and boundaries” through “Experiment and publication gates.” All relative paths belong to a **new independent repository named `correction-aware-memory`**, never another project. Document prepared October 17, 2026; implementation commands below are proposed and have **not been run**.

## Global constraints

- Start offline with deterministic fixtures; no model downloads or GPU are required for Tasks 1–4.
- Assume an existing Mac M4 Pro with 24 GB unified memory; verify actual hardware. NVIDIA GPU access is unconfirmed. Purchase no compute or API usage automatically.
- Model work must be optional: unavailable acceleration cannot block the datastore, baseline, dataset, or evaluator.
- Use synthetic public-release scenarios. Exclude private career records, email, resumes, credentials, and personal memory files.
- Store original observations and every decision immutably; the model cannot write SQL, invent source identities, alter trust metadata, or execute document instructions.
- Keep test labels, future events, and privileged reference answers outside inference inputs and training selection.
- Any CUDA performance claim requires an actual NVIDIA run. Apple MPS measurements are reported as Apple MPS.
- A reliable negative experiment is an acceptable result. Accuracy gains, novelty, publication, and resource fit are hypotheses.

## Review Focus

1. **Late stale documents:** arrival order must not overwrite newer effective facts; `test_late_stale_is_no_op` in Task 3.
2. **Correction versus real change:** a retrospective correction must preserve what was previously known, while a new effective state preserves historical truth; `test_bitemporal_correction_and_change` in Task 2.
3. **Duplicate and concurrent ingestion:** replay must be idempotent and stale proposals must fail atomically; `test_duplicate_and_revision_conflict` in Task 2.
4. **Untrusted text and fabricated evidence:** document instructions, forged references, invalid spans, or model-supplied authority must not bypass validation; `test_injection_and_forged_provenance` in Task 3.
5. **Entity/trajectory and answer leakage:** paraphrases, aliases, future labels, and duplicate templates must not contaminate splits or model inputs; `test_split_and_prompt_leakage` in Tasks 4–5.

## Purpose and boundaries

The candidate already has evidence of production computer vision, RAG, deployment, and PyTorch training. The gap is **new documented evidence** of adapter fine-tuning, rigorous memory evaluation, and reproducible research, not an assumption of missing ability. This project adds a saved adapter, an auditable training corpus, controlled comparisons, and a concrete account of when a small model helps.

The central question is: **Does correction-focused LoRA SFT reduce stale memory and false overwrites on unseen entities and writing styles, beyond prompting and transparent rules?** The distinguishing angle is temporal correction reliability, not inventing memory actions or claiming distillation itself is new.

Concrete synthetic example: an experiment report observed October 1 says `release_state=preliminary`, effective October 1. A release notice observed October 8 says `release_state=published`, effective October 7: **supersede**, retaining the earlier state. A document arriving October 9 repeats the October 1 preliminary status: **no_op**, not reinforcement of the published claim. A signed correction observed October 10 says the release actually became `withdrawn` on October 7: **update** the October 7 assertion, preserving the earlier published assertion in the knowledge history. Queries can distinguish “what is true as of October 8, using today's knowledge?” from “what did we know on October 8?”

**MVP:** one scalar predicate per observation; exact entity/predicate matching; five actions; immutable SQLite event ledger; current and historical views; deterministic baseline; synthetic trajectories; direct-state scoring; prompted 0.6B model and LoRA comparison when feasible; CLI plus saved HTML/Markdown inspection report. The offline milestone is useful even before training is possible.

**Stretch:** 1.7B scale comparison, independently written style-transfer set, externally licensed benchmark transfer, optional localhost API, and then privileged-context self-distillation. **Non-goals:** full MEMORA reproduction, vector database, multi-agent orchestration, open-ended extraction, arbitrary entity resolution, reinforcement learning, autonomous personal memory, hosted service, or polished frontend. Do not add them to solve a weak experiment.

## Operational design and contracts

### Atomic input and output

Use typed dataclasses plus explicit JSON validation initially. Values are strings or `null`; allowed predicates and value vocabularies live in the dataset manifest. Explicit retraction uses `value=null`, with reason `retraction`; do not invent a sixth delete action. An unsupported or ambiguous observation produces `no_op` and a review flag.

`Observation` fields: `observation_id`, `trajectory_id`, `source_id`, `source_sha256`, `entity_id`, `predicate`, `value`, `effective_at` (UTC instant or null), `observed_at` (UTC ingestion instant), `evidence_start`, `evidence_end`, `text`, `authority` (`official|informal`), `corrects_observation_id` (nullable), and `correction_authorized` (boolean). Metadata comes from a deterministic loader or reviewed annotation, never the deciding model. Evidence offsets are half-open Unicode code-point offsets into exact source text. The value and effective date are candidate annotations in the MVP; full text extraction is explicitly outside scope. Report this limitation in every result.

Example complete observation:

```json
{
  "observation_id":"o8","trajectory_id":"t1","source_id":"release-8",
  "source_sha256":"<loader-computed-64-hex-digest>",
  "entity_id":"experiment-17","predicate":"release_state","value":"published",
  "effective_at":"2026-10-07T00:00:00Z","observed_at":"2026-10-08T00:00:00Z",
  "evidence_start":0,"evidence_end":51,
  "text":"Release state: published, effective 2026-10-07 UTC.",
  "authority":"official","corrects_observation_id":null,"correction_authorized":false
}
```

The digest placeholder is illustrative and must never enter an executable fixture. The loader computes hashes and checks offsets; the quoted example text is 51 code points.

`DecisionRequest` contains `observation`, `snapshot_revision`, and `candidate_versions` for the exact entity/predicate only. Each candidate exposes `version_id`, value, effective time, correction lineage, source references, and evidence available by observed time. Exclude gold action, future trajectory events, generator tags, and answers. For this bounded task include the full matching history up to 16 versions; reject longer input with `CONTEXT_LIMIT`, rather than silently truncating.

`Proposal` contains `action`, `target_version_id` (nullable), `value`, `effective_at`, `source_id`, `evidence_start`, `evidence_end`, `reason_code`, and `review_required`. Example:

```json
{"action":"supersede","target_version_id":"v1","value":"published",
 "effective_at":"2026-10-07T00:00:00Z","source_id":"release-8",
 "evidence_start":0,"evidence_end":51,"reason_code":"new_effective_state",
 "review_required":false}
```

Unknown keys are invalid. The proposer may select only existing version IDs and the input source/span/value/date. For `no_op`, target/value/date are null and reason is one of `stale|ambiguous|untrusted|irrelevant|duplicate|retraction_unsupported`; preserve input source/span. Backend-created `DecisionEvent` adds `event_id`, immutable request/proposal, `status=committed|rejected`, validation codes, before/after revisions, and timestamps. `CommitResult` returns those identifiers and whether fact state changed. Rejected events remain auditable without changing the fact-state revision.

### Action semantics and temporal state

| Action | Preconditions and effect |
|---|---|
| `create` | No timeline for the key, trusted non-null value and effective date; append its initial version. |
| `reinforce` | Target the latest accepted effective boundary only; the observation must have that same effective boundary and value. Link distinct supporting provenance without changing value or boundary. Repeats referring to older boundaries are `no_op(stale)`, even when they accurately describe that historical value. Repeated source does not increase support count. Authorized historical corrections remain `update`. |
| `supersede` | Official changed value at a strictly later boundary than the target; target is the last timeline boundary, and no later boundary exists. Append a new version, deriving the old interval's end. Future-effective notices remain pending until queried time reaches their boundary. |
| `update` | Explicit authorized correction references a stored observation, same entity/predicate and same effective boundary; replace that boundary's winning assertion through an appended correction lineage. Require official source, authorization, and the current lineage head as target. This can correct a historical boundary without changing a later boundary. |
| `no_op` | Store observation/decision only; no fact mutation. Includes unresolved equal-time conflicts and stale contradictory assertions lacking authorized correction. |

MVP deliberately declines late insertion of previously unseen historical boundaries; mark it `ambiguous` for review. It supports late repetition and explicit corrections. A newer observed time alone never grants authority or establishes an effective date. Informal disagreement cannot overwrite official knowledge. Different entity or predicate is a different key. Reinforcement is provenance accumulation, not a calibrated confidence score.

Define `view(entity_id, predicate, *, effective_as_of, known_at)`: replay accepted events with `observed_at <= known_at`; choose the newest correction head at each boundary; select the greatest boundary `<= effective_as_of`. Derive half-open effective intervals from neighboring boundaries; never rewrite old ledger rows. An explicit null assertion means “retracted/unknown,” not permission to fall back to an obsolete value. Return selected version, value, status, interval, and source IDs, or absent.

All fixture ingestion is sequential in nondecreasing observed time; reject a historical `observed_at` supplied after newer ingestion. Out-of-order **effective** time remains supported under the preceding rules. Idempotency key is `(observation_id, source_sha256)`; same ID/different payload is an error. Repeated identical requests return the original result. Use SQLite transaction plus compare-and-swap snapshot revision; conflict returns `REVISION_CONFLICT`, with no partial version/support changes. Do not silently repair malformed output into another action. Retry conflicts by fetching a new snapshot and recording a new attempt.

The validator checks schema, UTC/date consistency, key and target membership, metadata equality, source hash/span existence, authorization, and action preconditions. It cannot prove natural-language entailment: source-grounding quality is independently annotated and evaluated. Separate model proposal correctness from committed-state correctness so policy guards do not hide a poor model.

### Proposed interfaces and repository map

```text
correction-aware-memory/
  pyproject.toml                  # core + optional ml dependency groups
  src/cam/
    contracts.py                 # dataclasses, enums, strict JSON parsing
    store.py                     # ledger, transactions, temporal projection
    policy.py                    # validator and deterministic proposer
    data.py                      # fixtures, generator, split manifests
    prompts.py                   # label-free model request rendering
    models.py                    # optional model adapter; no core imports
    train.py                     # optional LoRA SFT and masking checks
    evaluate.py                  # replay, metrics, clustered intervals
    cli.py                       # argparse command contract
    report.py                    # static inspection report
  configs/{offline,base,sft}.json
  data/fixtures/                 # small hand-authored sources + gold
  tests/test_{contracts,store,policy,data,prompts,models,train,evaluate,cli}.py
  docs/{dataset-card,model-card,methods,results,novelty-audit}.md
  runs/                          # ignored by default; sanitized examples released
```

Public Python interfaces: `Store(path: Path)`; `Store.snapshot(observation: Observation) -> DecisionRequest`; `Store.commit(request: DecisionRequest, proposal: Proposal) -> CommitResult`; `Store.view(entity_id: str, predicate: str, *, effective_as_of: str, known_at: str) -> FactView`; `validate(request: DecisionRequest, proposal: Proposal) -> list[str]`; `propose_rule(request: DecisionRequest) -> Proposal`; `render_request(request: DecisionRequest) -> list[dict[str,str]]`; `ModelProposer(config: ModelConfig).propose(request: DecisionRequest) -> Proposal`; `generate_dataset(config: DataConfig, out_dir: Path) -> DatasetManifest`; `train_adapter(config: TrainConfig) -> TrainingManifest`; `evaluate(config: EvalConfig) -> EvalReport`; `write_report(report: EvalReport, out_dir: Path) -> Path`. Definitions of manifest/config/report dataclasses live in `contracts.py`; never introduce a second incompatible schema.

### CLI and configuration contract

Every command emits a JSON summary; exit `0` success, `2` invalid input/config, `3` unavailable optional runtime, `4` failed correctness gate. It writes only under its explicit output directory. `--offline` forbids remote access, including automatic model downloads; model mode requires an already cached pinned revision. No missing model silently falls back to a rule result.

Future commands, run from the new repository after implementation:

```bash
python -m cam.cli check --fixtures data/fixtures --offline
python -m cam.cli generate --config configs/offline.json --out data/generated --offline
python -m cam.cli evaluate --config configs/offline.json --out runs/rule --offline
python -m cam.cli evaluate --config configs/base.json --out runs/base --offline
python -m cam.cli train --config configs/sft.json --out runs/sft --offline
python -m cam.cli report --run runs/rule --out runs/rule/report --offline
python -m pytest tests -q
```

JSON config uses `schema_version=1`; sections `data` (manifest path, split, seed), `proposer` (`rule|qwen`, model ID/revision, adapter path, device), `generation` (max input 2048 tokens, max new 256, nonthinking mode, sampling parameters, decoding `unconstrained|schema`), `training` (LoRA parameters, epochs, seed), and `evaluation` (seeds, bootstrap count, QA mode). Reject unknown keys, unset revisions in model runs, test split in training, and unequal comparison manifests. Validate token budgets before generation; no silent truncation. Store fully resolved config with each run. Defaults are proposed experimental controls, not recommended universal Qwen settings.

## Data, training, and controlled evaluation

Create world-state trajectories first, render documents second, derive gold actions/state transitions with an independent reference specification, then manually audit. Include stable repetition, authorized corrections, genuine changes, delayed stale reports, future-effective changes, retractions, informal conflict, distractors, and malicious document instructions. Keep semantic eligibility metadata explicit: the task is deciding memory action given bounded annotations, not resolving arbitrary trust from prose.

Planning defaults, adjustable after profiling: 50 pilot trajectories with 6–10 events each; later 600 training, 100 development, and 150 final-test trajectories, with up to three train-only paraphrases per event. These counts are neither power calculations nor performance guarantees. Treat pilot as development forever. Use fictional entities and original templates released under an explicit chosen dataset license (proposed CC0 for wholly original fixtures); code licensing is separate. Maintain per-artifact origin, license, attribution, generator/version/seed, author/reviewer, hash, and whether redistribution is allowed. Do not copy research benchmark text just because the paper is readable.

Split **before** rendering/augmentation: group connected entities, aliases, trajectories, and source templates; keep each connected group in exactly one split. Reserve separate template families/domains for a style-transfer slice. Deduplicate exact text and normalized near-duplicates across splits; regenerate offending groups instead of moving individual examples. Save split IDs and checksums. No model-generated paraphrase of a test trajectory enters training. Freeze final tests before model/prompt selection; access them once for the registered comparison. New hypotheses after viewing results require a fresh holdout or explicitly exploratory label.

Audit at least 50 pilot events, including every action type, manually against both action and state. Before final evaluation independently review a stratified 100-event sample and all ambiguous cases; if a second reviewer is unavailable label the audit single-reviewer. Report disagreement counts, adjudication rules, exclusions, and their timing. LLM judges may assist exploratory natural-text evaluation but never define canonical labels or certify themselves.

**Pretraining research gate:** first compare the rule baseline with independently reviewed pilot labels and state projections, before selecting or spending resources on LoRA. In this annotated-input MVP, metadata may determine every correct action. If the rule reaches the audited ceiling, write that finding and do not run a training campaign to claim a learned-memory improvement. An optional tiny SFT run is an educational structured-rule-imitation control, explicitly labeled as such; it cannot establish a research advantage over the rule. A harder raw-text interpretation study would need a separately specified input/output contract, new human labels and preregistered holdout, with candidate value/date/correction hints removed from model inputs. Do not quietly add extraction or change the final test to rescue the hypothesis.

Conditional training progression: rule baseline → prompted `Qwen/Qwen3-0.6B` → LoRA SFT → optional `Qwen/Qwen3-1.7B`. Proceed beyond the pilot only when the preceding gate justifies the stated experiment. Model cards provide nonthinking chat-template support; use it consistently. Proposed SFT defaults: rank 16, alpha 32, dropout 0.05, `q_proj`/`v_proj`, learning rate 2e-4, at most 3 epochs, microbatch 1, accumulation 16, maximum sequence 2048. Verify actual module names. Use completion-only cross-entropy over canonical JSON targets, with tested prompt masking and no packing initially. Choose checkpoint by development stale rate subject to false-overwrite non-regression, then macro-F1; record selection rule before running. Start with a 20-example overfit smoke test, not a full sweep. Gold rule-generated targets are supervised training, **not** evidence of external-teacher distillation.

Benchmark CPU/MPS support with a tiny forward/backward pass before committing to training. Do not assume bitsandbytes/QLoRA, FlashAttention, BF16, or CUDA on Apple hardware. If MPS fails or memory is insufficient, preserve a CPU smoke test, finish offline artifacts, and mark adapter training pending compatible hardware. Never claim a dry run is a trained adapter. No automatic paid fallback.

Compare all deployable arms on identical observations, snapshots, evidence, temporal guards, prompt budgets, and commit logic. Report rule accuracy on annotated inputs honestly: perfect performance can mean this bounded task requires rules. Include an intentionally weak latest-arrival baseline as a diagnostic, not the strongest comparator. A larger local reference is optional and must use the same test examples; do not buy API calls. Compare base versus SFT under the same decoding mode; if schema-constrained decoding is available for both, run a paired 2×2 base/SFT × constrained/unconstrained control. If unavailable, use identical strict parse/reject with no repair and narrow claims accordingly. Report invalid proposals separately from semantic errors.

Metrics, including denominators and per-trajectory values:

- **Action macro-F1:** mean of five action F1s on raw proposals; invalid output is an incorrect prediction. Print class support and per-class precision/recall.
- **Stale-active rate:** gold key/time checkpoints where an obsolete value remains selected divided by checkpoints whose gold state has changed. Also print missing-state rate so always-no-op cannot appear safe.
- **False-overwrite rate:** non-mutating gold opportunities where the committed semantic value changes divided by all non-mutating opportunities; report extra erroneous mutations among all commits separately.
- **State exact match/coverage:** correct value, effective boundary, retraction status, and history projection at every checkpoint; distinguish current-time and historical queries.
- **Provenance precision/recall:** claimed supporting source links that actually support the selected assertion divided by claimed links, and recovered gold supporting links divided by expected links. Hash/span validity is a separate mechanical metric.
- **Downstream QA:** deterministic key-and-time questions first, exact value plus source match. Optional language answers use one frozen answer model/retriever across arms. Full-history answering is a reference with disclosed larger context, not an equal-budget system. Never feed future observations.
- **Resources:** p50/p95 end-to-end and model-only latency, tokens, rejection rate, peak process/device memory, hardware/backend, model load separately. Record failures and warmup policy.

Use training seeds 11/22/33 when feasible, matched across arms; report actual run count if fewer. For stochastic inference use matched decoding seeds; greedy inference still has backend nondeterminism. Bootstrap paired arm differences by whole trajectory (2,000 resamples, 95% percentile intervals), retaining all its events; average within seed then report seed variation separately. Do not pretend correlated events or three seeds are thousands of independent samples. Register the primary stale-rate contrast and report other endpoints as secondary; wide intervals mean uncertainty, not equivalence.

## Eight independently testable implementation tasks

Each task follows: add named failing tests → run its focused command and observe expected failure → implement the listed contract → rerun to pass → inspect diff → commit if Git is initialized. Expected failures must come from missing behavior, not broken tooling. All commands are future instructions.

### Task 1: Typed contracts and hand-authored fixtures

**Files:** create `pyproject.toml`, `src/cam/contracts.py`, `data/fixtures/`, `tests/test_contracts.py`. **Consumes:** this schema. **Produces:** all named request/result/config dataclasses, strict `parse_observation(payload: dict) -> Observation` and `parse_proposal(payload: dict) -> Proposal`.

- [ ] Write `test_actions_and_utc_schema`, `test_span_hash_and_unknown_fields`: five actions parse; non-UTC/missing required metadata/unknown fields fail; fixture hashes and exact spans match.
- [ ] Run `python -m pytest tests/test_contracts.py -q`; confirm failure, implement parsing plus 12 small fixtures covering all actions, rerun for PASS.
- [ ] Review that no private data or ML imports entered core; commit `feat: define correction memory contracts`.

### Task 2: Immutable transaction ledger and temporal projection

**Files:** create `src/cam/store.py`, `tests/test_store.py`. **Consumes:** Task 1 dataclasses. **Produces:** `Store` and its four specified methods; SQLite observation/event/version/support tables with unique idempotency constraints.

- [ ] Write `test_bitemporal_correction_and_change`: before October 10 knowledge, October 8 resolves published; afterward resolves withdrawn; October 2 remains preliminary; later boundary remains unaffected by correction of an earlier boundary. Assert original rows unchanged.
- [ ] Write `test_duplicate_and_revision_conflict`: duplicate returns same event, changed-payload duplicate fails, two requests sharing revision cannot both mutate, rollback leaves no orphan support. Add future-effective and retraction tests.
- [ ] Run `python -m pytest tests/test_store.py -q`; implement replay and transactional compare-and-swap to PASS. Commit `feat: persist immutable temporal memory`.

### Task 3: Safe policy and deterministic proposer

**Files:** create `src/cam/policy.py`, `tests/test_policy.py`. **Consumes:** requests and store contract. **Produces:** `validate` and `propose_rule` with action table exactly as specified.

- [ ] Add `test_late_stale_is_no_op`, `test_injection_and_forged_provenance`, `test_equal_time_conflict_requires_review`, `test_informal_cannot_overwrite`, and `test_reinforcement_deduplicates_support`. Explicitly repeat an older true value after a newer effective boundary and assert `no_op(stale)` rather than historical reinforcement. Assert fabricated target/source/span or authority changes reject without state change; injected text is inert.
- [ ] Run `python -m pytest tests/test_policy.py tests/test_store.py -q`; implement hard preconditions and conservative rule decisions; expect PASS and zero fixture invariant violations.
- [ ] Review unsupported historical insertion is flagged, never silently accepted; commit `feat: validate and propose atomic memory actions`.

### Task 4: Reproducible trajectories and frozen splits

**Files:** create `src/cam/data.py`, the minimal pilot-scoring path in `src/cam/evaluate.py`, `configs/offline.json`, `tests/test_data.py`, `tests/test_evaluate.py`, `docs/dataset-card.md`. **Consumes:** typed contracts, the rule policy, and policy-independent expected timelines. **Produces:** `generate_dataset` and hashed `DatasetManifest` with split groups, licensing, gold actions/checkpoints, plus `evaluate(config: EvalConfig) -> EvalReport` for deterministic rule replay; Task 7 extends the same interface with model comparisons and statistics.

- [ ] Add `test_seed_reproduces_manifest`, `test_split_and_prompt_leakage` (data half), `test_reference_oracle_is_not_policy_call`, and `test_all_actions_and_stale_cases_present`. Assert aliases/augmentations stay within split and style-transfer templates are absent from train.
- [ ] Add a hand-counted rule-pilot scoring test with one deliberate proposal error, asserting raw action and committed-state metrics separately. Run `python -m pytest tests/test_data.py tests/test_evaluate.py -q`; implement seeded generation, group-first splitting and minimal deterministic replay; PASS with byte-identical repeated manifests and hand-matching counts. Manually audit pilot labels; commit `feat: generate auditable correction trajectories`.

### Task 5: Prompted-model boundary

**Files:** create `src/cam/prompts.py`, `src/cam/models.py`, `configs/base.json`, `tests/test_prompts.py`, `tests/test_models.py`. **Consumes:** `DecisionRequest`. **Produces:** `render_request`, `ModelProposer`, cached-revision model loading, optional schema decoding behind an explicit capability flag.

- [ ] Add `test_split_and_prompt_leakage` (prompt half): sentinel gold labels/future events/teacher references never render; evidence and current candidates do. Add fake-runtime tests for unknown IDs, malformed JSON, context overflow, and absent cache returning exit 3.
- [ ] Run `python -m pytest tests/test_prompts.py tests/test_models.py -q`; implement with injected fake generation for offline tests, PASS without downloading models.
- [ ] When cached hardware/runtime is available, run 10 development requests, save raw outputs/config/latency. Otherwise mark smoke test pending; commit `feat: add optional small model proposer`.

### Task 6: LoRA SFT with a verifiable mask

**Files:** create `src/cam/train.py`, `configs/sft.json`, `tests/test_train.py`, `docs/model-card.md`. **Consumes:** frozen training manifest, `render_request`, model config. **Produces:** `train_adapter` and manifest containing data/model/config/checkpoint hashes.

- [ ] Apply the pretraining research gate using pilot development labels and Task 4's minimal deterministic evaluator. Record `research_training`, `educational_imitation_only`, or `training_not_justified` with evidence in `docs/methods.md`; the last outcome skips expensive training without failing engineering completion.
- [ ] Write `test_prompt_tokens_have_no_loss`, `test_test_split_training_rejected`, `test_base_weights_frozen`, and `test_adapter_reload_matches_saved_output`. Use tiny fake or locally available test model; heavyweight tests explicitly skip with reason when runtime is absent.
- [ ] Run `python -m pytest tests/test_train.py -q`; implement completion masking and PEFT configuration; core tests PASS. Inspect effective trainable module names and parameter counts.
- [ ] On compatible hardware only, perform 20-example overfit/reload smoke test, then planned dev-selected training. Log unavailable training honestly; commit `feat: train and record correction LoRA adapters`.

### Task 7: Replay evaluator and honest statistics

**Files:** create `src/cam/evaluate.py`, `tests/test_evaluate.py`, `docs/methods.md`. **Consumes:** frozen manifests, any proposer, shared validator/store. **Produces:** `evaluate` returning raw proposals, committed states, metric denominators, paired trajectory statistics, and resource records.

- [ ] Add `test_metric_denominators_on_known_errors`, `test_invalid_output_counts_as_error`, `test_qa_cannot_see_future`, `test_bootstrap_resamples_whole_trajectory`, and `test_comparison_rejects_mismatched_manifest`. A hand-scored 10-event case must reproduce exact expected counts, including an always-no-op arm's missing-state failures.
- [ ] Run `python -m pytest tests/test_evaluate.py -q`; implement deterministic scorer and paired bootstrap to PASS. Save separate raw-proposal and post-guard results; commit `feat: evaluate correction reliability and uncertainty`.

### Task 8: CLI, inspection artifact, and release package

**Files:** create `src/cam/cli.py`, `src/cam/report.py`, `tests/test_cli.py`, `docs/results.md`, `docs/novelty-audit.md`; update dataset/model cards. **Consumes:** all interfaces above. **Produces:** exact CLI commands plus `write_report`, reproducible sanitized run package and explicit completion status.

- [ ] Add `test_offline_end_to_end_without_ml`, `test_cli_exit_codes`, and `test_report_matches_run_counts`: generate → rule evaluate → report succeeds with network disabled and no ML dependencies; report totals match saved raw records.
- [ ] Run `python -m pytest tests -q` and the three offline check/generate/evaluate commands above; require PASS, replay-identical states, and zero invariant violations. Open generated report and verify one create/change/correction/stale example visibly matches the ledger.
- [ ] Run model comparisons only when available; publish exact missing/skipped arms, seed count, license restrictions, and limitations. Commit `docs: package reproducible memory experiment`.

## First session, acceptance, and stop conditions

**First session deliverable:** finish Tasks 1–2's minimal fixtures and ledger path, then one conservative rule replay if time permits. Produce an auditable preliminary → published → stale → corrected trace with both time axes. No training download is needed to make concrete progress. A provisional 32–60 person-hour scope corresponds to roughly 4–6 weeks only when most of 8–10 hours/week goes to this project. The current planning assumption is 8–10 hours/week total across all three projects, so calendar duration will be longer under a split allocation. Re-estimate after the pilot and resource check.

**Deterministic correctness gate:** all specified invariant/contract tests pass; no partial writes; idempotent replay; correct effective/known-time projections; split audit clean; metrics match hand counts; offline CLI reproducible. Zero fixture invariant violations is an implementation requirement, not a claim of semantic perfection on arbitrary text.

**Experiment success gate:** complete the predeclared comparison with traceable data/config/model revisions, matched controls, uncertainty, and an explanation of failure slices. Training success requires a real saved/reloadable adapter, not only training code. A positive claim additionally requires an improvement supported by its paired interval without an unexplained false-overwrite regression. If unavailable hardware prevents training, release the offline benchmark as a partial milestone and explicitly leave fine-tuning pending.

Stop expanding after one reasonable prompt, one SFT configuration plus a small development adjustment, and the registered evaluation. If rule accuracy is effectively perfect because supplied metadata determines everything, investigate a clearly labeled extension with less explicit annotation; do not manufacture harder tests after seeing final results. If models only improve JSON formatting, report that and constrain claims. If no meaningful failure pattern appears in the pilot, stop the research branch and keep the engineering artifact.

## Experiment and publication gates

Primary hypothesis: correction-focused examples improve unseen-trajectory stale rate over matched prompted base, while false-overwrite rate does not worsen. Ablate correction examples at equal training-token budget; compare generic balanced SFT versus correction-focused SFT; remove effective-time distinction as an intentionally weakened control; compare with/without shared guards in sandbox replay only. Keep the complete safe deployment path for the main comparison. Include held-out styles and, only with lawful accessible artifacts, external transfer.

Before calling it novel, search primary literature on memory update policies, bitemporal databases, temporal knowledge editing, intrinsic memory evaluation, small-model SFT, and distillation. Record nearest approaches, overlapping contributions, and the remaining falsifiable difference in `docs/novelty-audit.md`. Existing papers already cover memory operations and intrinsic evaluation; a new name or adapter is insufficient. A workshop or reproducibility paper may be appropriate only after a literature audit, reliable baselines, and independent review. No submission or acceptance is promised.

PSD is a separate optional experiment **after ordinary SFT works**: freeze an SFT teacher adapter, provide privileged gold context only to its teacher prompt, align teacher/student logits on the same rollout tokens, and compare with ordinary SFT at matched examples and training budget. Do not describe teacher-text SFT as full PSD. Teacher/reference leakage into inference invalidates the experiment. Require tiny-example loss/alignment tests and a new preregistered holdout before implementation. Skip if resource cost or uncertain reproduction outweighs diagnostic value.

Release: code commit and lockfile; environment/hardware/backend manifest; model/tokenizer revision; prompt/template hashes; dataset licenses/splits/generator seeds; raw predictions and transaction failures; trained adapters when allowed; dataset/model cards; methods, results with intervals and negative findings; offline replay instructions; limitations covering synthetic annotations, small samples, limited predicate vocabulary, absent external validation, and untested runtimes. Do not claim full end-to-end extraction or independent research certification.

## Primary-source ledger

All entries verified **October 17, 2026**. Research results below are author-reported, not reproduced here. Source descriptions are deliberately brief; the design above is an original proposal rather than a reproduction claim.

1. [PSD: Pseudo Self-Distillation of Memory Representation Capabilities for LLM Agents, v1](https://arxiv.org/html/2609.23449v1). Purpose: motivate LoRA SFT and optional privileged-context distillation. Table 5 and §7.4 report overall LongMemEval SFT/PSD scores of .55/.53 (0.6B), .73/.68 (1.7B), and .78/.77 (4B): PSD trails SFT at each scale. These point estimates do not establish statistical significance. Table 4 compares a 100-question subset against full-benchmark baselines; our arms use identical examples. No identifiable implementation repository was located in the inspected paper. Availability, exact loss replication, and compute needs remain unverified; this plan does not depend on its code.

2. [Beyond Downstream QA: Rethinking How We Evaluate Agent Memory, v1](https://arxiv.org/html/2610.22209v1). Purpose: justify direct memory-state checks alongside QA. FEB-30 supplies 30 synthetic fact-evolution trajectories and illustrates intrinsic/extrinsic divergence, with judge-dependent scoring. It does not establish broad real-world reliability. Its advertised [benchmark repository](https://github.com/amazon-science/feb-30-benchmark) returned HTTP 404 from the GitHub API on this verification date. That may reflect availability or access; do not infer a license or assume downloadable artifacts. Build original fixtures and revisit external transfer separately.

3. [Qwen3-0.6B official model card](https://huggingface.co/Qwen/Qwen3-0.6B) and [Qwen3-1.7B official model card](https://huggingface.co/Qwen/Qwen3-1.7B). Purpose: model identity, license, chat formatting, and nonthinking mode. Cards expose Apache-2.0 licensing and document `enable_thinking=False`. Pin actual model/tokenizer commits and preserve notices when distributing derived artifacts. Card generation suggestions do not establish the optimal setting for this bounded JSON task; development controls and hardware feasibility still require testing.

4. [LoRA original paper](https://arxiv.org/abs/2106.09685) and [official PEFT LoRA reference](https://huggingface.co/docs/peft/main/package_reference/lora). Purpose: low-rank adapter method and actual configuration interface. LoRA freezes base parameters and trains low-rank changes; PEFT exposes rank, scaling, dropout, and target-module selection. Neither source guarantees this project's rank, resource fit, or accuracy. Resolve and pin installed API versions; `main` documentation can change.

5. [Official TRL SFTTrainer documentation](https://huggingface.co/docs/trl/main/en/sft_trainer). Purpose: SFT dataset/loss masking and PEFT integration. It documents completion-only and assistant-only loss with chat-template requirements. This plan chooses explicit completion supervision and requires a token-mask test; do not assume setting a flag alone excludes the prompt correctly. Pin a compatible release and test adapter save/reload. No training execution was performed while preparing this document.

## Copy-paste kickoff for any implementing AI

> Create a NEW independent repository named `correction-aware-memory` and implement the attached standalone plan. All relative paths refer to that repository. Start with Tasks 1–2: strict contracts, original synthetic fixtures, and immutable bitemporal ledger; then proceed sequentially through independently verified tasks. Do not read private career files, purchase compute, use paid APIs, or silently download models. Keep ML dependencies optional and finish offline data, policy, and evaluation even without a GPU. Verify official dependency/model docs before choosing versions. Treat numerical training/data defaults as adjustable proposals; record deviations before final-test access. Preserve action semantics, shared validation, immutable provenance, split isolation, and separate raw model errors from committed-state metrics. Mark every skipped/unavailable experiment explicitly. Stop after the scoped MVP and report actual artifacts, checks, limits, and the next unfinished task; do not claim adapter training, CUDA performance, novelty, or publication without evidence.
