# Correction-Aware Memory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended by the generic workflow) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. For this project, direct execution is the proposed default because the ledger, policy, and evaluator share tightly coupled contracts; independent review is useful at milestones. Delegated implementation requires the user's choice.

**Goal:** Produce a reproducible memory-reliability project whose implementation, experiments, and demonstrated judgment give a hiring reviewer concrete reasons to trust the user's skills.

**Architecture:** Typed atomic observations enter a deterministic envelope; rules or a small model propose an action, and one validator/SQLite transaction path governs all commits. Immutable history supports effective-time and knowledge-time queries. An independent synthetic oracle supplies a gold-history proposal-classification track and a separate closed-loop state-reliability track; saved reports distinguish raw proposal errors from accumulated state errors.

**Tech Stack:** Python 3.12, SQLite, pytest, JSON and static HTML/Markdown; optional pinned PyTorch/Transformers/PEFT/TRL/Datasets for Qwen3-0.6B and LoRA. Resolve actual dependency pins during implementation.

**Spec:** [First-release design](../specs/2026-10-17-correction-aware-memory-design.md), plus its referenced [original handoff](../handoffs/correction-aware-memory.md). Read both. This plan is proposed, not executed; all commands and test outcomes below are future acceptance instructions.

## Global Constraints

- Start offline. Paid API and cloud budget is $0. No automatic model downloads.
- Use original synthetic data only; no personal memory, email, resumes, or credentials enter fixtures, prompts, or training.
- One scalar predicate per observation; exact entity/predicate matching; five actions; immutable provenance; both effective time and knowledge time.
- Model proposals pass through the same validator and transaction path as rules.
- Keep model imports optional; never silently substitute rule outputs for an unavailable model.
- No training/test leakage, gold labels in inference inputs, future events in snapshots, or silent context truncation.
- No vector database, agent platform, arbitrary extraction, entity resolution, hosted API, polished frontend, or cross-project integration in this release.
- No claim of a trained adapter, model advantage, novelty, CUDA performance, or publication without corresponding evidence.

## Review Focus

1. Duplicate identity with changed metadata, revision races, and invalid proposals must leave no partial state or extra support: Task 2.
2. Corrections to old boundaries, future notices, and retractions must preserve both time axes and prevent obsolete-value fallback: Tasks 2–3.
3. Malicious instructions, forged spans/provenance, historical repetitions, and equal-time conflicts must not silently mutate memory: Task 3.
4. Template/alias leakage, future information, gold fields, and trainer truncation must not contaminate inputs or reported results: Tasks 4–6.
5. Missing state, zero denominators, invalid model output, and unavailable model arms must remain visible rather than becoming good-looking scores: Tasks 4–8.

## Workspace, task order, and file ownership

Planning lives in `Projects/1/`; implementation will live in a new independent `/Users/sragh/Downloads/Projects/correction-aware-memory/` repository. All paths below are relative to that repository. At execution, inspect for existing work before creating it. Copy the approved documents and handoff into `docs/superpowers/`, updating relative links. Commit locally after verified deliverables; do not push or publish as part of this plan.

| Files | Responsibility | Introduced |
|---|---|---|
| `pyproject.toml`, lockfile, `.gitignore` | Isolated core environment and optional ML extras | Task 1 |
| `src/cam/contracts.py` | Strict observation/proposal and configuration/result types; add later types only when needed | Task 1 onward |
| `data/fixtures/<case>/` | Original observations, separately stored gold proposals/checkpoints, manifest/vocabulary/hashes | Task 1 |
| `src/cam/store.py`, `src/cam/policy.py` | Immutable transactions, projection, validator; then rule proposer | Tasks 2–3 |
| `src/cam/data.py`, `src/cam/evaluate.py` | Seeded trajectories, independent oracle, replay and scoring | Task 4; extended Task 7 |
| `src/cam/cli.py`, `src/cam/report.py` | Working offline commands and report first; add ML commands later | Task 4 onward |
| `src/cam/prompts.py`, `src/cam/models.py` | Label-free rendering and optional inference runtime | Task 5 |
| `src/cam/train.py` | Optional completion-only LoRA training, mask validation and reload | Task 6 |
| `configs/{offline,base,sft}.json` | Strict, versioned experiment settings | Tasks 4–6 |
| `tests/conftest.py`, `tests/test_*.py` | Hand-authored test inputs, focused tests, offline integration proof | Every task |
| `docs/{dataset-card,model-card,methods,results,novelty-audit}.md`, `README.md` | Provenance, experiment decisions, actual results and reviewer entry point | Tasks 4–8 |
| `runs/` | Ignored full outputs; sanitized fixture-sized example run explicitly tracked | Task 4 onward |

Dependency order: **1 → 2 → 3 → 4 → Release A/training gate → 5 → 6 → 7 → 8**. Task 8 can package Release A while model tasks remain explicitly pending. Build the validator with the store in Task 2, instead of exposing an unvalidated ledger while waiting for Task 3.

## Task 1: Strict contracts and original fixture cases

**Files:** create project/configuration files, `src/cam/{__init__,contracts}.py`, `tests/{conftest,test_contracts}.py`, and `data/fixtures/<case>/{observations.jsonl,gold.jsonl,checkpoints.jsonl,manifest.json}`.

**Interfaces:** `parse_observation(payload: dict) -> Observation`; `parse_proposal(payload: dict) -> Proposal`; `ContractError(ValueError)`. Preserve all fields and five actions in the handoff. Test fixtures `observation_payload: dict`, `proposal_payload: dict`, and `canonical_case_dir: Path` provide the first canonical observation/proposal and its directory. Gold stays outside observation payloads.

- [x] **Step 1: Establish the isolated test environment.** Recheck instructions/status, create only the independent repository, explicitly use Python 3.12, declare core/test dependencies, and lock them. Add optional ML extras later. Verify `uv run --python 3.12 python --version`; expect 3.12.x. Verify pytest discovery works before interpreting a missing implementation as a valid failing test.
- [x] **Step 2: Add failing contract tests.** Write `test_actions_and_utc_schema`, `test_span_hash_and_unknown_fields`, `test_same_id_changed_metadata_is_distinct_payload`. Check fixed UTC parsing, null values, required trust metadata, exact Unicode offsets, and full-payload hashing. Representative assertions:

```python
assert parse_observation(observation_payload).authority == "official"
with pytest.raises(ContractError):
    parse_observation({**observation_payload, "authority": "model_asserted"})
with pytest.raises(ContractError):
    parse_proposal({**proposal_payload, "sql": "DELETE FROM versions"})
```

- [x] **Step 3: Run the focused tests.** `uv run python -m pytest tests/test_contracts.py -q`; expect missing parser/validation behavior. Environment failures are setup failures, not the intended red result.
- [x] **Step 4: Implement contracts and 12 fixture cases.** Cover the four-event canonical trace plus reinforcement, duplicate replay, revision conflict, historical correction, future-effective state, retraction, informal conflict, equal-time conflict, injection, and Unicode evidence. Compute source hashes from exact UTF-8 text; compare canonical full-payload hashes for identity. Keep schema parsing separate from policy judgment.
- [x] **Step 5: Verify and commit.** Rerun focused tests; expect PASS. Inspect fixture data and imports for private information or mandatory ML dependencies. Commit `feat: define correction memory contracts`.

## Task 2: Validated immutable ledger and temporal queries

**Files:** create `src/cam/store.py`, validator in `src/cam/policy.py`, `tests/test_store.py`; extend contracts/conftest.

**Interfaces:** `Store(path: Path)`; `snapshot(observation: Observation) -> DecisionRequest`; `commit(request: DecisionRequest, proposal: Proposal) -> CommitResult`; `view(entity_id: str, predicate: str, *, effective_as_of: str, known_at: str) -> FactView`; `validate(request: DecisionRequest, proposal: Proposal) -> list[str]`. Test-only `apply_case(store: Store, case_dir: Path) -> list[CommitResult]` reads explicit expected proposals, snapshots and commits them; it never calls the rule policy.

- [x] **Step 1: Add failing store tests.** Write `test_bitemporal_correction_and_change`, `test_duplicate_and_revision_conflict`, `test_rejected_attempt_allows_new_snapshot_retry`, `test_invalid_proposal_is_atomic`, `test_retraction_does_not_revive_old_value`, `test_future_effective_notice`, `test_observed_time_high_water_mark`. Replay the canonical fixture with `apply_case` and assert:

```python
assert store.view("experiment-17", "release_state", effective_as_of="2026-10-08T00:00:00Z", known_at="2026-10-09T00:00:00Z").value == "published"
assert store.view("experiment-17", "release_state", effective_as_of="2026-10-08T00:00:00Z", known_at="2026-10-10T00:00:00Z").value == "withdrawn"
assert store.view("experiment-17", "release_state", effective_as_of="2026-10-02T00:00:00Z", known_at="2026-10-10T00:00:00Z").value == "preliminary"
```

Also compare persisted original rows before/after correction; replay duplicates; submit two requests from one revision at the same observed timestamp; assert only one mutation initially succeeds and no orphan support exists. Retrying the rejected immutable observation with a fresh snapshot must succeed, preserve the rejected event, and return a distinct attempt event; repeating the exact rejected attempt returns its original rejection. Once committed, observation replay returns its original committed result. Changed metadata under the same observation ID must fail even with the same source hash. Reinforcement with new support advances revision without setting `fact_state_changed`.
- [x] **Step 2: Confirm failure.** `uv run python -m pytest tests/test_store.py -q`; expect missing store/transaction behavior.
- [x] **Step 3: Implement the transaction boundary and validator together.** Append observations/events/versions/support; enforce immutable source registry, action preconditions, observed-time order, idempotency, exact source/span/value/date membership, and compare-and-swap revision inside the SQLite transaction. Separate the unique canonical request/proposal attempt key from observation identity and its committed-result pointer; rejected attempts remain auditable and do not block a valid retry. Derive both temporal views by replay; cached projections must be rebuildable. Apply every contract clarification in the design.
- [x] **Step 4: Verify and commit.** `uv run python -m pytest tests/test_contracts.py tests/test_store.py -q`; expect PASS including rollback and immutable-history assertions. Commit `feat: persist validated temporal memory`.

## Task 3: Conservative rule proposer and adversarial replay

**Files:** extend `src/cam/policy.py`; create `tests/test_policy.py` and any extra original fixtures needed.

**Interfaces:** `propose_rule(request: DecisionRequest) -> Proposal`; consume the same `validate`, `Store.snapshot`, and `Store.commit` as every later arm.

- [x] **Step 1: Add failing policy tests.** Write `test_canonical_actions`, `test_late_stale_is_no_op`, `test_injection_and_forged_provenance`, `test_equal_time_conflict_requires_review`, `test_informal_cannot_overwrite`, `test_reinforcement_deduplicates_support`, `test_same_value_later_boundary_requires_review`, and `test_context_limit_counts_correction_versions`. For canonical chronological snapshots:

```python
assert actions == ["create", "supersede", "no_op", "update"]
assert stale_proposal.reason_code == "stale"
assert ambiguous_proposal.review_required is True
assert forged_commit.status == "rejected"
```

`actions` is collected by proposing/committing each canonical observation in sequence. `stale_proposal` is observation 3; ambiguous and forged results come from their named fixtures. Explicitly test old-but-true repetition after a newer boundary and rejected mutation with fabricated evidence/source/target.
- [x] **Step 2: Confirm failure.** `uv run python -m pytest tests/test_policy.py -q`; expect missing proposer behavior.
- [x] **Step 3: Implement the action table.** Use supplied metadata and current candidate history; do not interpret injected instructions or infer authority from prose. Same-boundary authorized correction targets the current lineage head, including historical boundaries. Unsupported historical insertion/equal-time conflicts require review. No additional action or extraction subsystem.
- [x] **Step 4: Verify and commit.** `uv run python -m pytest tests/test_contracts.py tests/test_store.py tests/test_policy.py -q`; expect PASS and zero fixture invariant violations. Save the canonical trace for the next milestone. Commit `feat: propose conservative correction memory actions`.

## Task 4: Independent pilot, honest scoring, and working offline report

**Files:** create `src/cam/{data,evaluate,cli,report}.py`, `configs/offline.json`, `tests/test_{data,evaluate,cli}.py`, `docs/{dataset-card,methods}.md`; extend contracts.

**Interfaces:** `generate_dataset(config: DataConfig, out_dir: Path) -> DatasetManifest`; `evaluate(config: EvalConfig) -> EvalReport`; `write_report(report: EvalReport, out_dir: Path) -> Path`; internal scorer `_compute_metrics(records: list[dict]) -> dict`. `records` are joined scoring records containing predictions, committed checkpoints, and oracle labels after inference; they are never model inputs. Config parsing uses handoff `schema_version=1` and its declared sections. CLI merges the explicit `--out` path into typed runtime config.

- [x] **Step 1: Add failing generation/scoring tests.** Write `test_seed_reproduces_manifest`, `test_split_and_prompt_leakage` (data part), `test_reference_oracle_is_not_policy_call`, `test_all_actions_and_stale_cases_present`, `test_metric_denominators_on_known_errors`, `test_zero_denominator_is_null`, and `test_always_no_op_has_missing_state`. A test-only hand-counted scoring fixture has 4 changed checkpoints, one obsolete selection, 5 non-mutating opportunities and one false overwrite:

```python
assert metrics["stale_active_rate"] == {"numerator": 1, "denominator": 4, "value": 0.25}
assert metrics["false_overwrite_rate"] == {"numerator": 1, "denominator": 5, "value": 0.2}
assert empty_metrics["stale_active_rate"] == {"numerator": 0, "denominator": 0, "value": None}
```

These arithmetic fixtures test the scorer independently; they do not assert that an impossible guarded mutation occurred. Separately verify actual replay counts by hand and that an always-no-op proposer exposes missing state. Add `test_offline_end_to_end_without_ml` and `test_report_matches_run_counts` using a socket/network-denial fixture and an environment with only core/test dependencies.
- [x] **Step 2: Confirm failure.** `uv run python -m pytest tests/test_data.py tests/test_evaluate.py tests/test_cli.py -q`; expect missing pipeline behavior.
- [x] **Step 3: Implement Release A.** Generate world timelines before rendering documents; derive oracle actions/checkpoints without importing/calling `propose_rule`, `validate`, or `Store.view`. Split entity/alias groups and template families before augmentation; pilot stays development-only. Generate 50 pilot trajectories of 6–10 events. Implement separate gold-history one-step proposal scoring and independent closed-loop state replay, with explicit track tags on saved outputs; fixed gold action labels are used only with gold-history requests. Build `check`, `generate`, `evaluate` (rule only), and `report` now, rather than postponing the usable demo until training finishes. Save `resolved-config.json`, `manifest.json`, `predictions.jsonl`, `checkpoints.jsonl`, `metrics.json`, the SQLite ledger, hashes, and provenance under the explicit run directory. Report values and text must be HTML-escaped.
- [x] **Step 4: Verify the complete offline path.** Run the following from a clean core/test environment; each command must exit 0, and repeated generation/replay must preserve dataset hashes and projected states. Runtime timestamps can differ.

```bash
uv run python -m pytest tests -q
uv run python -m cam.cli check --fixtures data/fixtures --offline
uv run python -m cam.cli generate --config configs/offline.json --out data/generated --offline
uv run python -m cam.cli evaluate --config configs/offline.json --out runs/rule --offline
uv run python -m cam.cli report --run runs/rule --out runs/rule/report --offline
```

- [x] **Step 5: Audit and record the training gate.** Prepare a readable 50-event audit sample covering every action; the user or another actual human reviews it when available. Record reviewer identity/count, disagreements and exclusions honestly. Write `research_training`, `educational_imitation_only`, or `training_not_justified` with pilot evidence in `docs/methods.md`. Without human review, mark labels unaudited and scientific validation pending; do not pretend the agent's review is independent human evidence. Commit `feat: release offline memory benchmark and report`.

**Milestone acceptance:** an outsider can run the commands and inspect the canonical correction trace. Record observed rule results without treating a perfect annotated-input score as a learned-memory contribution.

## Task 5: Pinned prompted-model boundary

**Files:** create `src/cam/{prompts,models}.py`, `configs/base.json`, `tests/test_{prompts,models}.py`; extend CLI/contracts/optional dependency group.

**Interfaces:** `render_request(request: DecisionRequest) -> list[dict[str, str]]`; `ModelProposer(config: ModelConfig).propose(request: DecisionRequest) -> Proposal`. Inject a fake generation callable in tests. Preserve raw text, parse errors, latency and selected revision in run outputs.

- [x] **Step 1: Add failing boundary tests.** Write `test_split_and_prompt_leakage` (prompt part), `test_unknown_ids_and_malformed_json_rejected`, `test_context_overflow_is_explicit`, `test_no_cached_model_is_unavailable`, and `test_optional_ml_not_imported_by_offline_cli`. Construct a sentinel-labeled fixture and assert:

```python
assert "GOLD_ACTION_SENTINEL" not in rendered_text
assert "FUTURE_EVENT_SENTINEL" not in rendered_text
assert completed.returncode == 3  # unavailable explicitly requested model
```

Also enforce `CONTEXT_LIMIT` for more than 16 assertion versions and input token overflow; neither returns a silently truncated request.
- [x] **Step 2: Confirm failure.** `uv run python -m pytest tests/test_prompts.py tests/test_models.py -q`; expect missing boundary behavior, with no network access.
- [x] **Step 3: Implement optional inference and runtime probe.** Verify/pin compatible official library APIs and a Qwen3-0.6B model/tokenizer commit. The user must explicitly choose a download if weights are absent; offline commands never fetch them. Use `enable_thinking=False`, a single fixed prompt, 2048 input-token and 256 generated-token budgets, strict JSON parse/reject, and matched base/SFT decoding. Use a recorded deterministic nonthinking decoding baseline (`do_sample=False`) as a project default, then test it on development examples; do not describe it as Qwen's general recommendation.
- [x] **Step 4: Verify and, if cached weights permit, run ten development requests.** Unit tests must pass with fake generation. Real smoke output includes exact revision, CPU/MPS backend, dtype, latency, process memory, raw responses and failures. Probe a tiny forward/backward pass before promising training support. Missing weights/runtime leaves the real smoke explicitly pending. Commit `feat: add optional pinned small model proposer`.

## Task 6: Conditional LoRA training and adapter proof

**Files:** create `src/cam/train.py`, `configs/sft.json`, `tests/test_train.py`, `docs/model-card.md`; extend CLI/contracts and methods.

**Interfaces:** `train_adapter(config: TrainConfig) -> TrainingManifest`. Manifest records data/model/tokenizer/config hashes, actual module names/trainable counts, seed, runtime, adapter paths and adapter file hashes. Keep the handoff's completion-only training contract.

- [ ] **Step 1: Enforce the Task 4 gate before a training campaign.** `training_not_justified` skips actual model optimization. `educational_imitation_only` permits a tiny transparent imitation control when the user wants training evidence; it is labeled accordingly. An undocumented or unaudited gate cannot support a research-advantage claim.
- [ ] **Step 2: Add failing training tests.** Write `test_prompt_tokens_have_no_loss`, `test_test_split_training_rejected`, `test_base_weights_frozen`, `test_overlength_example_is_rejected_before_trainer`, and `test_adapter_reload_matches_saved_output`. Use tiny fake/local models for core tests; mark heavyweight runtime tests separately. Required mask/parameter assertions:

```python
assert all(label == -100 for label in prompt_labels)
assert any(label != -100 for label in completion_labels)
assert all(not parameter.requires_grad for parameter in frozen_base_parameters)
assert saved_greedy_tokens == reloaded_greedy_tokens
```

- [ ] **Step 3: Confirm failure.** `uv run python -m pytest tests/test_train.py -q`; expect missing masking, gate or training behavior.
- [ ] **Step 4: Implement the smallest supported SFT path.** Use rank 16, alpha 32, dropout 0.05, `q_proj`/`v_proj`, learning rate 2e-4, max 3 epochs, microbatch 1, accumulation 16, sequence max 2048, packing off. Preflight token lengths; TRL's own truncation must not silently change the task. Start seed 11, preserve prompt/completion masks, and choose checkpoints by development stale rate with false-overwrite non-regression, then macro-F1. Do not assume BF16, bitsandbytes, FlashAttention or CUDA support on MPS.
- [ ] **Step 5: Verify smoke training before scaling.** First overfit 20 development/training-only examples, save the adapter, reload onto the exact base revision, and reproduce fixed greedy development outputs. Record actual losses and results, including failure. Estimate full-run compute from the probe; paid alternatives need an exact cost/run proposal. Then run the justified registered training, or leave the adapter milestone pending. Core tests passing alone never satisfies training completion. Commit `feat: train and verify correction memory LoRA adapters` only if that accurately describes the implemented capability.

## Task 7: Matched comparisons, ablations, and uncertainty

**Files:** extend `src/cam/evaluate.py`, `tests/test_evaluate.py`, experiment configs, `docs/{methods,results}.md`.

**Interfaces:** extend the existing `evaluate(config: EvalConfig) -> EvalReport`; preserve Task 4 report/CLI compatibility. Add internal `_paired_bootstrap(paired_counts: list[tuple[int, int, int, int]], *, seed: int, resamples: int = 2000) -> tuple[float | None, float | None]`. Each tuple contains one complete trajectory's `(base_numerator, base_denominator, sft_numerator, sft_denominator)`. Sample paired trajectory rows and recompute pooled rates from summed counts; preserve/report zero-denominator draw counts in the surrounding evaluation output.

- [ ] **Step 1: Add failing comparison tests.** Write `test_invalid_output_counts_as_error`, `test_qa_cannot_see_future`, `test_bootstrap_resamples_whole_trajectory`, `test_bootstrap_pools_counts_after_trajectory_resampling`, `test_comparison_rejects_mismatched_manifest`, `test_each_arm_has_independent_store`, `test_action_labels_use_gold_history_only`, `test_recovery_action_is_not_scored_against_wrong_context`, and `test_seed_variation_not_pooled_as_events`. Minimal bootstrap sanity check:

```python
assert _paired_bootstrap([(0, 1, 0, 1), (0, 1, 0, 1)], seed=11) == (0.0, 0.0)
```

Use deterministic recorded sampling in the nontrivial bootstrap test to assert complete trajectory blocks stay intact. Use unequal denominators such as `(10, 100, 0, 100)` and `(1, 1, 0, 1)` to distinguish the pooled contrast `-11/101` from the incorrect mean contrast `-0.55`; cover all-zero-denominator draws. Simulate missing the initial `create`, then a valid recovery `create` when the gold-history label would be `reinforce`; only the separate gold-history proposal is eligible for fixed-label action F1. Every invalid output must remain in the appropriate track's raw-error denominator, even when the validator prevents a state error. Check actual environment/model failure becomes an unavailable arm, not a scored rule replacement.
- [ ] **Step 2: Confirm failure.** `uv run python -m pytest tests/test_evaluate.py -q`; expect absent comparison/statistics behavior.
- [ ] **Step 3: Implement full scoring and preregister the comparison.** Preserve all original handoff metrics, supports, denominators, current/historical checkpoints, provenance and deterministic QA. Freeze the 600/100/150 train/dev/test split and held-out style slice before selection. Use identical gold-history requests across arms for raw action F1; independently replay identical observations/checkpoints from an empty store per arm for closed-loop state reliability, allowing error histories to diverge naturally. Track inference cost separately for both passes. Main arms: rule, prompted base, correction-focused SFT. For a correction-focused research claim, add equal-training-token balanced-SFT and no-correction controls. Keep latest-arrival and guard-removal sandbox ablations visibly diagnostic. Run optional constrained/unconstrained pairing only when supported equally. Record warmup, p50/p95 latency, memory and failures; a changed config invalidates a matched comparison.
- [ ] **Step 4: Verify and execute only justified comparisons.** Focused tests PASS. Finish the actual 100-event/all-ambiguous label audit before final result inspection where independent review is available; otherwise disclose the limitation. Register the pooled stale-rate contrast, false-overwrite and missing-state constraints, seeds 11/22/33 when feasible, 2,000 trajectory-level bootstrap resamples and 95% intervals. Access the locked final test for this comparison; new hypotheses require a fresh holdout or exploratory label. Record true run/seed count and null results. Commit `feat: compare memory reliability with trajectory uncertainty`.

## Task 8: Reviewable release and hiring evidence

**Files:** finalize `README.md`, `src/cam/report.py`, `tests/test_cli.py`, cards/methods/results, `docs/novelty-audit.md`; track one sanitized example run outside ignored bulk runs.

**Interfaces:** final CLI preserves handoff commands and JSON summaries; exit codes `0` success, `2` invalid input/config, `3` unavailable optional runtime, `4` failed correctness gate. Commands write generated artifacts only to their explicit output path; no implicit cache/model downloads. Include a runnable report-only path that never invokes a model.

- [x] **Step 1: Add failing release tests.** Extend `test_cli_exit_codes`, `test_offline_end_to_end_without_ml`, `test_report_matches_run_counts`, `test_report_escapes_untrusted_text`, and `test_output_directory_boundary`. Include success, bad config, absent runtime and correctness-failure cases. Assert static report counts equal saved `metrics.json`, injected markup is escaped, and user-specified output boundaries are respected.
- [x] **Step 2: Confirm failure, implement only the missing release behavior, and rerun.** `uv run python -m pytest tests/test_cli.py -q`; expect initial failure for missing behavior and then PASS. Do not add a service/frontend to improve the demo.
- [x] **Step 3: Verify the deliverable from a clean environment.** Run the complete Task 4 offline command sequence and full tests. Model/training commands run only when their pinned cached runtime exists; list skipped arms precisely. Open the HTML report and visually confirm create/change/correction/stale examples, both time axes, source spans, metric denominators, and unavailable-result labels. Test the README reproduction instructions verbatim.
- [x] **Step 4: Write evidence-linked project claims.** README: two-sentence problem, canonical demo, architecture, reproduction, actual results, limitations and links to raw run/adapter artifacts. Distinguish engineering implementation, automated tests, human label review, and experimentally measured model outcomes. A short local walkthrough shows the correction trace and one reproduced run. Keep numbers and saved-adapter claims absent until measured. Record nearest primary related work before any novelty claim; publication research and PSD remain later gates, not release requirements.
- [x] **Step 5: Review and commit the release package.** Check all spec requirements against artifacts, inspect the diff and licenses/attribution, and commit locally. Report changed files, actual checks and outputs, artifact paths, unresolved compute/reviewer requirements, and the next unfinished task. Push, publication and outreach require a separate instruction.

## Planning self-review and handoff

Coverage: Tasks 1–3 implement schemas, invariants, time semantics and action policy; Task 4 supplies the independent offline experiment and first report; Tasks 5–6 provide optional real inference/training; Task 7 covers every comparison metric/ablation and uncertainty requirement; Task 8 packages exact reproduction and honest completion status. The five Review Focus items each have owning tests above. Original public signatures are preserved; internal test/scoring helpers are defined where introduced.

Estimated active effort and stopping gates are in the design: Release A 14–24 hours; full conditional scope 32–60 hours, approximately 4–8 weeks at 8–10 hours/week devoted to this project. Compute duration is unmeasured. The next concrete action is Task 1, followed by the smallest validated canonical trace; no model download is needed to start.

Recommended execution is direct implementation with a fresh review at Release A and before the final release. The user has requested planning, so no implementation, dependency installation, repository creation, training, or publishing is authorized by this document alone.


## Execution status — October 17, 2026

The user authorized implementation with “start working”. Tasks 1–4 and Release A Task 8 are complete, with reviewed fixes and portable evidence. Task 5 is complete, including the explicitly authorized pretrained download and ten-request CPU smoke: 0/10 proposals passed the schema, and the four-token backward probe passed. Raw failures and resource measurements are published without repair or prompt tuning. Tasks 6–7 remain deferred under the research-training gate; no adapter or learned-model advantage is claimed. The current suite passes 89 tests with the optional ML extra (88 passed, one native API check skipped in the isolated core environment). See docs/progress.md for the persistent execution record.
