# Related work and novelty status

Status: **no novelty claim**. This is an independently specified engineering MVP inspired by primary-source work; no paper was reproduced experimentally here.

- [PSD: Pseudo Self-Distillation of Memory Representation Capabilities for LLM Agents](https://arxiv.org/html/2609.23449v1) studies small-model memory construction using SFT and privileged-context distillation. This release does neither; a future ordinary SFT adapter must not be described as full PSD.
- [Beyond Downstream QA: Rethinking How We Evaluate Agent Memory](https://arxiv.org/html/2610.22209v1) motivates direct memory-state checks alongside QA and includes synthetic fact-evolution trajectories. This project similarly checks state but uses original text, deterministic exact-key semantics and explicit trusted annotations. External benchmark redistribution or reproduction is not claimed.
- Immutable append-only events and effective/knowledge time are established database ideas. Five memory operations and an adapter would not establish novelty by themselves.

A paper hypothesis would still require a systematic primary-literature comparison with memory-update policies, bitemporal databases, temporal knowledge editing, intrinsic memory evaluation and small-model training; independent label review; a meaningful learned task; matched baselines/ablations; uncertainty and external/generalization evidence. No venue, submission or acceptance is promised.
