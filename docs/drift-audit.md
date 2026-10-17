# Alignment with the original folder 1 brief

Checked October 17, 2026 against `../1/small model memory that handles correction.md` in the local workspace. Its unchanged repository copy is [the source handoff](superpowers/handoffs/correction-aware-memory.md), byte-identical with SHA-256 `7ac059d03f0c9b00a32b7032f9c2edf83e9cc2412080df43b47c2003f182cd72`.

| Original requirement | State at this check |
|---|---|
| Five actions, immutable evidence, bitemporal queries, guarded transactions | Implemented; contract/adversarial/replay tests and original canonical trace |
| Independent synthetic oracle, deterministic rule pilot, saved inspection artifacts | Implemented; seed-11 pilot and raw records published |
| Pinned optional prompted Qwen runtime | Implemented; real CPU ten-request smoke recorded all ten schema failures without repair |
| Manual audit of at least 50 pilot events | Packet prepared; **0 actual human reviewers**, requirement still incomplete |
| Completion-only LoRA SFT, frozen base, saved/reloaded adapter | **Task 6 unfinished** before this continuation |
| Matched base/SFT/rule comparison, clustered uncertainty and full split controls | **Task 7 unfinished**; smoke requests are not this comparison |
| Model card, training corpus and reproducible adapter evidence | Await Task 6; no trained-adapter claim at this checkpoint |

The architecture and copied specification have not diverged. The project is an incomplete staged implementation of the original training-and-evaluation goal. Our recent emphasis on packaging the deterministic milestone and treating manual review as the only next action unnecessarily deferred the permitted educational SFT control.

The original brief explicitly permits a tiny SFT experiment as **educational structured-rule imitation**, while prohibiting a research-training campaign or learned-memory superiority claim when annotations let rules solve the task. The user has now requested continuing from that brief. Task 6 therefore proceeds in `educational_imitation_only` mode: 20 training examples, the specified LoRA settings, bounded local optimization, frozen-base verification, and an actual save/reload proof. Human audit remains honestly pending. No full training campaign, final holdout, new extraction task, prompt-tuning sweep, or paid compute is introduced.

The smoke saves its final bounded checkpoint rather than selecting a research winner. Record loss, exact-output behavior and any failure to overfit; a save/reload proof alone cannot establish memory improvement. Full development selection, matched comparison and uncertainty remain Task 7 work under the original gates.
