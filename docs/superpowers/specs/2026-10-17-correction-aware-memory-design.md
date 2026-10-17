# Correction-aware memory: first-release design

Prepared October 17, 2026. Status: proposed design for review; no product implementation or experiments have been performed.

## Intent and source of truth

The user chose Project 1 and wants it to demonstrate capabilities that earn trust and interviews. Their words: “that they can trust on my capabilities and skill and my i should stand out from the crowd and they can give me interview or job offer with it”. An interview or offer is the motivation, not a promised project outcome.

Build an inspectable demonstration of reliable memory changes, reproducible evaluation, and, when justified and feasible, real small-model adapter training. Someone should be able to understand the problem in two minutes, inspect one failure/correction trace, and reproduce an offline result without downloading a model.

The supplied [standalone handoff](../handoffs/correction-aware-memory.md) remains the detailed specification for schemas, action preconditions, metrics, and required tests. This document records the release priorities and clarifications needed to execute it. Where this document makes a new choice, it is an **agent-proposed default**, available for correction during review. Unchanged handoff requirements still apply.

## What the demonstration does

Use original synthetic experiment-release documents. One observation contains an exact entity/predicate, candidate value and effective date, trusted source metadata, and a text evidence span. These annotations are supplied; this MVP does not extract arbitrary facts or determine source authority from prose.

The system proposes one of five actions: `create`, `reinforce`, `supersede`, `update`, or `no_op`. A shared deterministic validator checks every proposal before a SQLite transaction can change memory. The ledger preserves the original observations, proposals, provenance, and correction history.

The central demo is:

| Arrival / knowledge time | Claimed effective time | Observation | Expected behavior |
|---|---|---|---|
| October 1 | October 1 | Preliminary release | Create the initial state |
| October 8 | October 7 | Published release | Supersede the earlier state |
| October 9 | October 1 | Delayed preliminary report | Ignore stale evidence for current-state mutation |
| October 10 | October 7 | Authorized correction: withdrawn | Correct the October 7 assertion and retain knowledge history |

After the last event, querying October 8 with October 9 knowledge returns `published`; querying October 8 with October 10 knowledge returns `withdrawn`. October 2 remains `preliminary`. A separate fixture covers reinforcement from a distinct source. Synthetic demo dates are fixed test data, independent of the run's wall clock.

## Release sequence and definition of done

**Release A: trustworthy offline memory benchmark.** Include strict contracts, validated atomic commits, temporal queries, hand-authored cases, a 50-trajectory pilot, an independently specified oracle, baseline evaluation, and a browsable static report. The CLI runs without ML packages, model weights, network, or a paid account. Label this as an engineering milestone; it is not a completed fine-tuning project.

**Release B: verified fine-tuning evidence, conditional on the pilot and runtime.** Add pinned Qwen3-0.6B inference, a tested training mask, a real saved/reloaded LoRA adapter, matched comparisons, and an explanation of model errors. If annotations make rules an exact solution, a small SFT experiment can demonstrate structured-rule imitation and improvement over a prompted model; it cannot establish superiority over the rule or a new memory method. A larger research training campaign requires evidence of a meaningful learned task. A missing runtime leaves Release B explicitly pending.

The hiring-facing package contains a clear README, the four-event trace above, one-command offline reproduction, a results table linked to raw outputs and manifests, and a concise explanation of design choices and limitations. Model results and adapter links appear only after those artifacts exist. A local 60–90 second walkthrough is useful after the demo works; posting, publishing, outreach, and account changes are separate actions.

## Scope constraints

- Core: Python 3.12, standard-library SQLite/JSON/hash tooling, pytest; optional PyTorch, Transformers, PEFT, TRL, and Datasets.
- Start offline. Paid API and cloud budget is $0. No automatic model downloads.
- Use original synthetic data only; no personal memory, email, resumes, or credentials enter fixtures, prompts, or training.
- One scalar predicate per observation; exact entity/predicate matching; five actions; immutable provenance; both effective time and knowledge time.
- Model proposals pass through the same validator and transaction path as rules.
- Keep model imports optional; never silently substitute rule outputs for an unavailable model.
- No training/test leakage, gold labels in inference inputs, future events in snapshots, or silent context truncation.
- No vector database, agent platform, arbitrary extraction, entity resolution, hosted API, polished frontend, or cross-project integration in this release.
- No claim of a trained adapter, model advantage, novelty, CUDA performance, or publication without corresponding evidence.

## Verified environment and setup defaults

Read-only inspection on October 17 found macOS 27.0.1, Apple M4 Pro, 24 GB unified memory, Python 3.12.9 available as `python3.12`, and approximately 46 GiB free disk space. The default `python3` is 3.14.7; explicitly select 3.12 for this project. `uv` and Git are available. Runtime/model fit has not been tested, and no cached-model availability is assumed.

Planning files live next to the supplied handoff. The proposed implementation repository is `/Users/sragh/Downloads/Projects/correction-aware-memory/`, which did not exist during inspection. Create it only when implementation begins; keep the three projects independent. Do not initialize Git in the parent directory or overwrite an existing repository. Copy the approved design, plan, and source handoff into the new repository's documentation with working relative links.

Resolve and lock compatible dependency versions at setup, then preserve the lockfile and environment details. Do not pin a guessed future combination in this planning document. Check current official APIs again before model setup; no CUDA-only packages are assumed on this Mac.

## Contract clarifications: proposed defaults

1. **Commit safety is part of the store from its first useful implementation.** `Store.commit` calls the common validator inside its transaction and checks snapshot revision before any fact/support mutation. Build the validator with the ledger; the rule proposer follows. This fixes the handoff's Task 2/Task 3 dependency without introducing a temporary unvalidated write path.
2. **Revision scope.** Use one monotonically increasing store revision initially. Accepted new assertions/corrections and new distinct supporting links advance it. `no_op`, rejected attempts, duplicate requests, and already-linked support do not. `fact_state_changed` means the semantic assertion timeline changed; reinforcement may advance the revision while this flag remains false. Do not use this flag as a shortcut for all writes.
3. **Idempotency and retries.** Preserve the handoff's observation identity key, and additionally compare a canonical hash of the entire observation payload. Same observation ID with changed metadata is invalid even if source text/hash is unchanged. The registry binds each source ID to immutable source text/hash. Separate observation identity from decision-attempt identity: derive an internal attempt key from the canonical request (including snapshot revision) and proposal. First check exact known attempts and return their original result, including an old rejection; otherwise, if the observation has a committed terminal result, return that result without mutation. A rejected attempt does not consume the observation's terminal-result slot; retrying against a fresh snapshot records a new immutable event. Any committed action, including `no_op`, fills that slot. All retries still satisfy observed-time ordering; test revision races at the same observed timestamp, and retry before ingestion advances past that timestamp. Do not rewrite observation time to make a retry fit.
4. **Temporal semantics.** Require timezone-aware UTC input, canonicalize accepted `Z`/`+00:00` timestamps to `Z`, and reject nonzero offsets. Future effective time is valid. Ingestion is nondecreasing in observed time, including audited no-op/rejection attempts; duplicate replay is checked first. Ties are ordered by immutable event sequence. Runtime timestamps are separately recorded and do not replace supplied observation time in temporal queries.
5. **Retraction and repeated values.** An official new later-boundary retraction is `supersede` with null value and reason `retraction`; an authorized same-boundary correction to unknown is `update` with null value. No initial null-valued `create`. A null head prevents fallback to an obsolete value. A same-value statement at a new boundary, absent a correction, is `no_op(ambiguous)` with review required; `reinforce` requires the same latest boundary. Preserve same-boundary null reinforcement if all normal support conditions hold.
6. **Bounded context.** Count all stored assertion versions, including correction lineage, toward the 16-version maximum. Reject excess with `CONTEXT_LIMIT`; never discard historical versions to make a request fit. Also enforce actual tokenizer budgets before model inference/training; explicitly reject overlength examples rather than letting a trainer truncate them.
7. **Decision audit.** Schema-valid rejected proposals are immutable ledger events. Unparseable model text is retained in the append-only run prediction log, scored incorrect, and never coerced into a valid proposal or committed. It need not masquerade as a typed `Proposal` in the transaction API. Parser errors and datastore rejection codes remain distinct.
8. **Data partitioning.** Assign connected entity/alias groups and template families to a split before rendering. Instantiate only templates owned by that split; never connect the entire corpus by reusing one template across every split. Pilot examples stay development-only. Preserve a separate held-out style/domain slice and exact/normalized duplicate audits.
9. **Metrics and undefined values.** Preserve every handoff metric with numerator/denominator and per-trajectory records. Undefined rates are JSON `null` with denominator 0, not numeric zero. Compute macro-F1 over the fixed five actions, recording missing class support. Invalid predictions count as errors. Separate raw proposals, committed semantic state, missing state, and mechanical provenance validity.
10. **Controlled comparison and action labels.** Use two explicitly separate evaluation tracks. For raw action macro-F1, render the same gold-history snapshot at each observation for every arm and compare raw proposals with the independently specified one-step label; inputs contain only legitimate history, never gold action/future events. For accumulated state reliability, run every arm from an empty independent store with the same ordered observations/checkpoints and let its snapshots diverge through its own errors. Score state against fixed gold checkpoints. Do not compare a recovery action in a diverged store with an incompatible gold-history action label, and do not feed corrected gold snapshots into this closed-loop track. Report raw-output errors for each track and account for the additional inference separately.

## Experiment design and gates

Begin with 12 hand-authored fixture cases and a 50-trajectory pilot of 6–10 events each. Audit at least 50 pilot events across all actions and inspect expected states; record who actually reviewed them. The AI cannot certify independent human review. If no human reviewer is available, release the automated engineering evidence with an explicit unaudited-label limitation and leave research claims pending.

Before training, record one gate outcome in `docs/methods.md`: `research_training`, `educational_imitation_only`, or `training_not_justified`. The expected risk is that exact annotated inputs determine the action, so the rule ceiling may be perfect. Do not manufacture benchmark difficulty or weaken the rule to obtain a model win. An expanded raw-text study would be a separate design and holdout.

If model work proceeds, use Qwen3-0.6B in nonthinking mode with a pinned model/tokenizer revision. First probe CPU/MPS with a tiny forward/backward pass and ten development requests; then attempt a 20-example overfit and adapter-reload test. Initial LoRA defaults: rank 16, alpha 32, dropout 0.05, `q_proj`/`v_proj`, learning rate 2e-4, at most 3 epochs, batch 1, accumulation 16, sequence limit 2048. Verify module names and completion-token masking; keep packing off. Profile before choosing dtype or promising full-run duration.

Later dataset defaults are 600 train, 100 development, and 150 final-test trajectories, with up to three training-only paraphrases per event. Freeze splits before prompt/model selection. Seeds are 11/22/33 when feasible, and actual seed count is disclosed. Reserve seed 11 for the first smoke experiment.

The main arms are deterministic rule, prompted base, and correction-focused SFT. A research claim about correction-focused training additionally requires matched balanced-SFT and no-correction controls at equal training-token budget. Use one prompt, one SFT configuration, and at most one development adjustment before the registered comparison. Optional constrained decoding is a paired base/SFT control only if the same backend supports it for both. Latest-arrival is a diagnostic weak baseline; the stronger rule stays visible.

The primary contrast is the difference in pooled stale-active rates for correction-focused SFT versus prompted base, subject to no false-overwrite or missing-state regression. Secondary outcomes are fixed-five-action macro-F1, state exact match/current and historical coverage, provenance precision/recall, deterministic QA, invalid-output rate, latency, and resource use. Report missing-state rate alongside stale rate. Resample complete trajectories 2,000 times for 95% paired percentile intervals, recomputing each arm's summed numerator/denominator within each draw; do not substitute an unweighted mean of trajectory rates. A draw with zero eligible denominator is undefined and counted/disclosed rather than assigned zero. Report seed variation separately. Do not infer equivalence from a wide interval.

Independent final label review, when available, covers a stratified 100-event sample and all ambiguous cases before final model results are inspected. Report real reviewer count, disagreements, and exclusions. Keep engineering completion and scientific validation separate.

## Effort, stopping points, and next action

Working budget remains the handoff's 8–10 person-hours per week total. Project 1 is the immediate focus; a continuing allocation across all three has not been agreed. The following are planning ranges, not measured work or deadlines:

| Milestone | Active effort | Reviewable result |
|---|---:|---|
| M0: contracts, validated ledger, canonical trace | 6–10 h | Immutable before/after memory with both time axes |
| M1: policy, pilot, offline evaluation/report | 8–14 h | Reproducible Release A and recorded training gate |
| M2: prompted small-model boundary | 4–8 h | Real raw predictions and runtime probe |
| M3: conditional LoRA/control experiments | 8–16 h | Saved/reloaded adapter and matched run manifests |
| M4: full comparison and hiring-facing package | 6–12 h | Evidence-linked results, README, demo, limitations |

Total 32–60 person-hours if all model milestones proceed; compute time is separate and unmeasured. At the full 8–10 h/week allocation, that is approximately 4–8 weeks. Release A is roughly 14–24 hours, or 2–3 focused weeks. Re-estimate after M0 and the pilot; other-project allocation lengthens the calendar. No fixed public deadline is being set.

The first implementation sitting starts with strict parsing and the original four-event fixture, then the smallest validated ledger path. It does not need to finish all of M0 in one sitting. The concrete next action after plan review is Task 1 of the implementation plan. Stop at Release A if the learned task is unjustified or compatible compute is unavailable; preserve its evidence and mark Release B pending or educational as appropriate.

## Primary sources checked for this plan

- [PSD paper, §5 and Table 5](https://arxiv.org/html/2609.23449v1): distinguishes ordinary SFT from privileged-context distribution-level training; full PSD remains a later optional experiment.
- [Beyond Downstream QA, benchmark design and limitations](https://arxiv.org/html/2610.22209v1): motivates direct state inspection; its external benchmark is not required by this MVP.
- [Official Qwen3-0.6B card](https://huggingface.co/Qwen/Qwen3-0.6B): documents nonthinking chat formatting. Generation suggestions still require bounded-task validation.
- [Official PEFT LoRA reference](https://huggingface.co/docs/peft/en/developer_guides/lora): configuration and target modules; version compatibility must be locked at implementation.
- [Official TRL SFTTrainer documentation](https://huggingface.co/docs/trl/en/sft_trainer): completion supervision and masking. Its documented automatic truncation is why this project must preflight lengths explicitly.

These sources were opened during planning, not reproduced experimentally. Their claims do not constitute project results.

## Builder-check disposition

A fresh builder reviewed this design and the handoff. Two material questions were resolved as agent-proposed implementation defaults: decision-attempt identity versus observation idempotency (clarification 3), and action labels after closed-loop state divergence (clarification 10). Both receive explicit tests in the implementation plan. Neither requires a new product preference from the user.
