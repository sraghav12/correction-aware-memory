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

## Work completed after the check

Task 6 now has completion-only token masking, a tested frozen-base LoRA loop, typed configs/manifests, explicit data/runtime gates, checkpoint hash/pin validation, and two actual saved/reloaded CPU adapters. Model/generation configuration classes now live in `contracts.py` as the original specifies, with existing `models` imports kept compatible.

The default 20-example run used six optimizer steps and matched 2/20 canonical targets. The original's one allowed small development adjustment changed only accumulation (16 to 1), preserving the same corpus, seed, base and initial adapter hashes, three epochs and all other recipe settings. It matched 13/20 targets. Both passed exact fresh-base reload and unchanged-base checks; **neither achieved the full overfit acceptance criterion**. All raw losses and failures remain published. [Model card](model-card.md) · [Default evidence](../examples/educational-sft/README.md) · [Single adjustment](../examples/educational-sft-overfit/README.md).

Task7 now has matched exploratory rule/base/both-adapter replay on the existing five development trajectories, a guarded latest-arrival diagnostic, all required rate denominators including erroneous mutations among commits, separate per-track resources, and paired trajectory intervals. [Evidence](../examples/development-comparison/README.md). This does not complete the full original research study.

Remaining original requirements: actual human audits, full frozen comparison splits/style transfer, independent training-seed variation, research-specific controls and guard-removal sandbox, development checkpoint selection, and a locked final evaluation. The full overfit acceptance criterion also remains unmet. No raw-text extraction, PSD, vector database, hosted application, or larger model was added to rescue the result.
