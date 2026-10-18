# Why my memory system keeps old answers

*Correction-aware memory — an independent project by [sraghav12](https://github.com/sraghav12). Python, SQLite, PyTorch and LoRA.*

On October 8, a notice says an experiment was published the previous day. On October 9, a delayed notice arrives, still describing its preliminary state on October 1. On October 10, an authorized correction withdraws the published result.

This is the fictional experiment in my [runnable demo](../examples/canonical-trace.json). The two later messages need different treatment. The delayed notice describes an older state. The correction revises the assertion that took effect on October 7. Keeping whichever message arrived last would lose that distinction.

Ask about October 8 using what was known on October 9: **published**. Ask about the same date using October 10's knowledge: **withdrawn**. The original published assertion still belongs in the record.

I built `correction-aware-memory` around those two clocks: when a fact applied, and when the system learned it. The question was whether a small language model could choose reliable memory updates under an explicit policy.

The first design decision was to separate the proposed update from the stored fact. A proposer chooses among creating, reinforcing, superseding, correcting or ignoring a claim. A deterministic validator checks the source, dates, authority, target and action preconditions before an atomic SQLite transaction. Corrections append versions linked to the assertions they replace. Previous rows remain intact.

That separation also matters for measurement. A rejected proposal is still a model error. It cannot quietly become a successful prediction because a guard prevented damage. I evaluated the raw decisions separately from the memory accumulated during replay. [Architecture and scoring](methods.md).

The rule baseline matched all **1,005 state checkpoints** in the [initial 50-trajectory synthetic pilot](results.md). There was a reason for that ceiling: the inputs already supplied the candidate value, dates, source authority and correction authorization. This task tested what to do with those annotations. It did not test extracting them from arbitrary documents or deciding which real-world source to trust.

I then tested a pinned **Qwen3-0.6B** with completion-only LoRA training on an M4 Pro CPU. I kept the control to twenty examples, three epochs and one adjustment. The first configuration reproduced **2 of 20** training targets exactly. Changing gradient accumulation reached **13 of 20**. Both missed the full 20-example overfit check. The saved adapters, unchanged base-weight hashes and exact reload checks establish that training and serialization worked; they do not establish that the model learned the task reliably. [Training evidence](model-card.md).

The matched development comparison made the gap concrete:

| Approach | Correct memory-state checkpoints |
|---|---:|
| Full rule policy | **103/103** |
| Guarded latest-arrival baseline | 91/103 |
| Adjusted LoRA model | 75/103 |
| Default LoRA model | 14/103 |
| Prompted base model | 0/103 |

These are **five synthetic development trajectories**, containing 44 observations and 103 checkpoints, with one training seed. The model arms shared a pinned base, prompt, decoding settings and token budgets. This is an exploratory comparison; the checkpoints are not 103 independent experiments. [Full results and recorded failures](../examples/development-comparison/comparison.md).

The 75/103 needed a second look. That same adjusted adapter matched the required value **and exact supporting source set** at only **29/103** queries. Its state score checked values, status and temporal boundaries; source support was measured separately. Reporting both exposed an audit-trail failure that the state score alone would have missed.

There was another misleading number: the base model had **zero stale states**. Its outputs failed validation and left memory empty at all 103 checkpoints. An empty store could look safe on the stale-state metric while answering nothing. Missing-state counts made that zero interpretable.

The rule policy therefore remains the useful implementation for this contract. The small-model control did not demonstrate an advantage or justify a larger training campaign. Its failed overfit check also limits the conclusion: this experiment cannot establish that small models generally fail at correction-aware memory. The broader research study and final evaluation remain unfinished.

I used AI coding agents to implement the system, run experiments and review the work. The project scope, release decisions and claims in this case study are my responsibility. A [separate API review](../examples/ai-label-review/README.md) and AI adjudication are recorded as such; the full human label audit remains incomplete. The repository preserves failed attempts alongside working code so a reader can inspect the evidence behind the result.

Start with the [four-event trace](../examples/canonical-trace.json), inspect the [matched comparison](../examples/development-comparison/README.md), or [run the offline demo](../README.md#see-the-behavior-first). The engineering result is a bounded, auditable memory system. A further learned-memory claim needs a task where the model has something necessary to infer beyond the supplied annotations.
