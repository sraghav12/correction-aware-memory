# Separate AI review of the pilot labels

Measured October 17, 2026 (America/New_York). At the user's request, a separate API model checked the existing 50-event development packet. This is an **AI consistency review**, not a completed human audit or a new result from the trained memory models.

The answer key was hidden: every request supplied only the current observation, its gold prior history and the effective/knowledge-time queries. Expected actions, expected states and previous human verdicts were omitted. Each case used an independent request. The policy prompt was written by the project author; trusted annotations, gold history and the oracle-derived query schedule were supplied. This is a check conditional on that contract, not independent validation of real-world truth or the task design.

## Preserved attempts

| Attempt | Completed answers | Action matches | Full proposal matches | Full state/provenance matches |
|---|---:|---:|---:|---:|
| Claude Haiku 5.5, default thinking | 18/50 | 18/50 | 18/50 | 34/114 |
| Claude Haiku 5.5, explicit thinking off | 0; credit-blocked preflight | Not evaluated | Not evaluated | Not evaluated |
| Gemini 2.5 Flash Lite via OpenRouter, thinking off | 50/50 | 39/50 | 32/50 | 67/114 |

The first attempt returned 49 HTTP successes: 31 exhausted the 1,500-token budget in thinking without a final answer, and one other request failed for insufficient credits. Of the 18 completed predictions, 17 matched all queried states (34/36 checkpoints); one used the wrong correction version ID. Nine otherwise matching cases included concerns and remain `unresolved` in that attempt's original comparison. The preserved whole-attempt denominator includes incomplete answers; do not interpret 18/50 as a semantic error rate among completed answers.

The explicit-thinking-off Anthropic follow-up used a different authorized credential, but all 50 token-count preflights returned insufficient-credit errors. It sent zero inference requests. The Gemini fallback was registered before its calls and used the same policy prompt and case inputs, JSON-object output mode and no reasoning. A single completion/configuration probe preceded the other 49 calls; correctness against the answer key was not a continuation condition. No responses were retried, repaired or substituted. Separate registrations disclose the changed provider/configuration; these attempts are not a controlled between-model benchmark.

For Gemini, 20 cases matched the complete proposal and every query; 30 had one or more differences. A full proposal includes source/span, target, dates, reason and review flag, beyond the action label. State matching includes value, status, effective interval, selected version and source set. Only UTC timestamp representation and source-set order are normalized. Schema-valid JSON alone did not establish correct memory reasoning.

## Adjudication and limits

A separate `gpt-6.1-sol` agent inspected every Gemini mismatch and all 18 completed Haiku outputs against the written specification and packet history. Its [per-case adjudication](gemini-fallback/adjudication.json) classifies the observed differences as reviewer-model errors; **no gold-label defect was established by this review**. Errors include dropping source support, confusing creation with reinforcement, mishandling null retractions, selecting future boundaries and using replaced correction heads. This adjudication is also AI-authored, with correlated-error and specification-dependence limitations; it does not certify that the labels are universally correct.

The project author separately recomputed current-source hashes and evidence spans. Repeated identical notice text legitimately has the same hash under different source IDs; this records provenance and does not establish independent corroboration. The written specification explicitly includes evidence at `observed_at <= known_at`. Intentionally missing-date cases require review in the expected policy; a model noting that ambiguity is not itself a newly discovered label defect.

One actual participant has accepted one case in a separate local human-review file. The other 49 human verdicts remain blank. AI predictions do not fill those fields. The original 50-event packet and its blank published template remain unchanged; the original full manual-audit requirement remains incomplete. This AI review permits continued engineering checks without asking the user to approve 49 more cases, but does not automatically authorize research training or close the original scientific validation requirements.

API usage for the first Anthropic attempt is estimated at **$0.045284** using the published rates; OpenRouter reports **$0.020671** for the 50 Gemini calls. Including the tiny connection probes, total estimated/reported inference usage is about **$0.066**, below the registered $0.15 cap. Token counts and provider-reported costs are preserved; this is not a billing statement. No additional training or final-test evaluation ran.

## Verify offline

```bash
python3 examples/ai-label-review/verify.py
```

This checks every artifact hash, the unchanged original packet, 50 unique cases/114 checkpoints, exact blind input joins, and replayed comparison counts from the saved final answers. It needs no API key or ML packages and sends no network requests.

Each attempt contains its prospective registration and exact requests. Response projections preserve final answer text, errors, stop reasons, usage and provider IDs; thinking/signature blocks are omitted from the public projection. Original complete responses stay in ignored local run storage, with their hashes recorded per response. [Manifest](manifest.json) binds the published artifacts. New API calls may differ because these are hosted model IDs, not locally pinned model weights.
