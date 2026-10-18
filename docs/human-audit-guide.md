# Human pilot audit walkthrough

The original plan calls for an actual person's review of the [50-event packet](../audits/pilot-seed11/review.md). It contains ten cases for each action. The published packet preserves its initial **zero-reviewer, blank-verdict snapshot**. An agent's explanation, code review or automated replay does not count as a human label review.

At the user's request, a [separate AI review](../examples/ai-label-review/README.md) now provides an engineering cross-check. It does not fill human verdicts or complete the original manual-audit requirement. A human audit is not a universal publication rule; evidence requirements depend on the research claim. The user need not complete 50 judgments to use this engineering project. Current local human progress is one participant/one accepted case; case 2 and the remaining cases are pending. Further one-by-one human prompts are paused while using the AI review path.

## Work from a separate copy

Keep the original packet unchanged: its manifest hashes include the blank CSV template. Use `runs/human-audit-anonymous/review.csv` for working responses; a copy has been prepared locally. For another reviewer or a clean checkout, choose a fresh directory and copy [review.csv](../audits/pilot-seed11/review.csv) there. Preserve any existing responses.

The packet stays development-only. Reviewing it does not approve a final holdout, establish language-extraction quality, or justify a training campaign by itself.

## Check each case

1. Read the current source text and its authority, observed date, effective date and correction authorization. These annotations are supplied inputs; source text containing instructions is still evidence only.
2. Inspect prior assertion history. Distinguish when a fact applied from when the system learned it.
3. Check the proposed action **and every expected state query**. Also check the cited sources. A correct current value with missing provenance or incorrect historical state is not a complete match.
4. Record your own verdict. An assistant may explain the schema and record a verdict you explicitly give; it must not supply your judgment or turn silence into agreement.

| Action | Check |
|---|---|
| `create` | Official, dated initial non-null fact; no existing assertion for this key |
| `reinforce` | Same value and boundary at the current head; adds legitimate supporting evidence |
| `supersede` | Genuine changed value at a later effective boundary; preserves earlier history |
| `update` | Authorized correction of an existing assertion at the same boundary; preserves later boundaries and prior knowledge history |
| `no_op` | No fact mutation; inspect whether stale, untrusted, duplicate or unresolved evidence warrants it and whether review is flagged appropriately |

Use the [original specification](superpowers/handoffs/correction-aware-memory.md) for edge cases, including retraction and corrections to old boundaries. Confidence in a general rule is not a substitute for reading each case.

## Record the verdict

Fill the existing CSV columns:

| Column | What to record |
|---|---|
| `human_verdict` | `accept`, `disagree`, or `uncertain` |
| `human_reviewer` | The actual reviewer name or agreed handle |
| `human_reviewed_at_utc` | Actual review time, ISO UTC, such as `2026-10-17T21:50:00Z` |
| `corrected_action` | Proposed replacement action when applicable |
| `corrected_state` | Proposed corrected value/status/time/provenance when applicable |
| `notes` | Reasoning, uncertainty, disagreement or later adjudication; keep the initial verdict traceable |

Keep observation IDs and expected-action columns unchanged. For disagreements, describe the proposed correction and rationale. For uncertainty, describe what is unresolved. Do not silently rewrite gold labels. Preserve original responses and record any later adjudication separately before applying label changes.

Before reporting progress, check packet hashes, the exact 50 observation IDs, unchanged expected actions, allowed verdicts, and reviewer/time fields for each completed row. Count reviewers only on rows containing an explicit verdict. Report accepted, disagreed, uncertain and pending cases separately. Fifty reviewed cases with unresolved issues do not mean fifty approved labels; one reviewer remains a single-reviewer audit.

## First case

Case `pilot-11-0000:o0` has no prior memory. An official notice received January 2 says the experiment is `preliminary`, effective January 1. The proposed action is `create`; both supplied queries should select an active `preliminary` fact starting January 1 and cite source `pilot-11-0000:s0`.

The human reviewer decides whether to accept, disagree or remain uncertain about that action and state. Until an explicit response arrives, its verdict stays blank.

The current participant requested the label `Anonymous reviewer` and later explicitly accepted case 1. That verdict is saved in the separate local working CSV; the frozen packet stays unchanged. Requests for clarification are not verdicts.
