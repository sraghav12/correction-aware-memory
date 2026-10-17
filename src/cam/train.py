"""Optional educational completion-only LoRA smoke training."""

from collections import Counter
from dataclasses import asdict
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import platform
import random
import resource
import time

from cam.contracts import (ContractError, GenerationConfig, ModelConfig, RuntimeUnavailable, TrainConfig,
                           TrainingManifest, canonical_json, digest, parse_observation, parse_proposal)
from cam.data import prepare_output, read_dataset, read_jsonl, write_json, write_jsonl
from cam.evaluate import CorrectnessError, run_environment
from cam.models import HuggingFaceRuntime, _unique_object
from cam.policy import validate
from cam.prompts import render_request
from cam.store import Store


def gold_requests(dataset):
    targets = {row["observation_id"]: parse_proposal(row["proposal"]) for row in dataset["gold.jsonl"]}
    rows = []
    with Store(Path(":memory:")) as store:
        for raw in dataset["observations.jsonl"]:
            observation = parse_observation(raw)
            request = store.snapshot(observation)
            target = targets[observation.observation_id]
            rows.append({"request": request, "target": target})
            if store.commit(request, target).status != "committed":
                raise ContractError("training gold-history target fails the shared guard")
    return rows


def training_corpus(path: Path, *, max_examples=20):
    manifest, dataset = read_dataset(path)
    if manifest["split"] != "train":
        raise ContractError("training corpus requires train split")
    if type(max_examples) is not int or not 5 <= max_examples <= 20 or max_examples % 5:
        raise ContractError("educational corpus must be 5..20 balanced examples")
    counts, selected = Counter(), []
    for row in gold_requests(dataset):
        action = row["target"].action
        if counts[action] < max_examples // 5:
            selected.append(row)
            counts[action] += 1
    if len(selected) != max_examples:
        raise ContractError("training corpus lacks examples for all five actions")
    return manifest, selected


def completion_example(tokenizer, request, target, *, max_sequence=2048):
    codes = validate(request, target)
    if codes:
        raise ContractError(f"invalid training target: {codes}")
    prompt_ids = tokenizer.apply_chat_template(render_request(request), tokenize=True, add_generation_prompt=True,
                    enable_thinking=False, truncation=False, return_dict=False)
    if not isinstance(prompt_ids, list) or any(type(token) is not int for token in prompt_ids):
        raise ContractError("tokenizer must return an explicit list of prompt token IDs")
    completion_ids = tokenizer.encode(canonical_json(target), add_special_tokens=False)
    if tokenizer.eos_token_id is None:
        raise ContractError("completion training requires an explicit EOS token")
    completion_ids = list(completion_ids) + [tokenizer.eos_token_id]
    input_ids = list(prompt_ids) + completion_ids
    if len(input_ids) > max_sequence:
        raise ContractError(f"CONTEXT_LIMIT: training sequence {len(input_ids)} exceeds {max_sequence}")
    return {"input_ids": input_ids, "attention_mask": [1] * len(input_ids),
            "labels": [-100] * len(prompt_ids) + completion_ids}


def configure_lora(model, settings):
    try:
        from peft import LoraConfig, TaskType, get_peft_model
    except ImportError as error:
        raise RuntimeUnavailable("optional PEFT dependency is absent") from error
    targets = [name for name, _ in model.named_modules() if name.endswith(("q_proj", "v_proj"))]
    if not targets or not any(name.endswith("q_proj") for name in targets) or not any(name.endswith("v_proj") for name in targets):
        raise ContractError("base model does not expose both q_proj and v_proj")
    model = get_peft_model(model, LoraConfig(r=settings.rank, lora_alpha=settings.alpha,
                           lora_dropout=settings.dropout, target_modules=["q_proj", "v_proj"],
                           bias="none", task_type=TaskType.CAUSAL_LM))
    model.peft_config["default"].base_model_name_or_path = settings.model.model_id
    model.peft_config["default"].revision = settings.model.revision
    if any(p.requires_grad for name, p in model.named_parameters() if "lora_" not in name):
        raise ContractError("base weights must remain frozen")
    return model


def parameter_digest(model, *, adapter):
    h = hashlib.sha256()
    for name, parameter in model.named_parameters():
        if ("lora_" in name) == adapter:
            h.update(name.encode())
            h.update(str(tuple(parameter.shape)).encode())
            h.update(memoryview(parameter.detach().cpu().contiguous().numpy()).cast("B"))
    return h.hexdigest()


def _tensors(example, torch, device):
    return {key: torch.tensor([example[key]], dtype=torch.long, device=device)
            for key in ("input_ids", "attention_mask", "labels")}


def mean_completion_loss(model, examples, torch, device):
    model.eval()
    with torch.inference_mode():
        losses = [float(model(**_tensors(example, torch, device), use_cache=False).loss.cpu()) for example in examples]
    if not all(math.isfinite(value) for value in losses):
        raise RuntimeUnavailable("nonfinite completion loss")
    return sum(losses) / len(losses)


def optimize(model, examples, settings, torch, *, log_path=None):
    if not examples:
        raise ContractError("training examples cannot be empty")
    trainable = [p for p in model.parameters() if p.requires_grad]
    optimizer = torch.optim.AdamW(trainable, lr=settings.learning_rate, weight_decay=0.0, foreach=False)
    epochs, steps = [], 0
    for epoch in range(settings.epochs):
        model.train()
        order = list(range(len(examples)))
        random.Random(settings.seed + epoch).shuffle(order)
        epoch_losses, started = [], time.perf_counter()
        for start in range(0, len(order), settings.accumulation):
            window = order[start:start + settings.accumulation]
            optimizer.zero_grad(set_to_none=True)
            for index in window:
                loss = model(**_tensors(examples[index], torch, settings.model.device), use_cache=False).loss
                value = float(loss.detach().cpu())
                if not math.isfinite(value):
                    raise RuntimeUnavailable("nonfinite training loss")
                (loss / len(window)).backward()
                epoch_losses.append(value)
                if log_path:
                    with Path(log_path).open("a") as stream:
                        stream.write(canonical_json({"epoch": epoch + 1, "example_index": index, "loss": value,
                                                    "microbatches_seen": len(epoch_losses), "optimizer_steps": steps}) + "\n")
            torch.nn.utils.clip_grad_norm_(trainable, 1.0, error_if_nonfinite=True)
            optimizer.step()
            steps += 1
        epochs.append({"epoch": epoch + 1, "mean_completion_loss": sum(epoch_losses) / len(epoch_losses),
                       "optimizer_steps": steps, "seconds": time.perf_counter() - started})
    optimizer.zero_grad(set_to_none=True)
    model.eval()
    return epochs


def _train_adapter(settings: TrainConfig):
    if settings.gate != "educational_imitation_only":
        raise RuntimeUnavailable("training gate is training_not_justified; no optimization performed")
    if settings.data.manifest is None or settings.development_manifest is None:
        raise ContractError("training and development manifests are required")
    if settings.output_dir.exists() and (not settings.output_dir.is_dir() or any(settings.output_dir.iterdir())):
        raise ContractError("training output directory must be empty")
    manifest, corpus = training_corpus(settings.data.manifest, max_examples=settings.max_examples)
    dev_manifest, dev_data = read_dataset(settings.development_manifest)
    if dev_manifest["split"] != "development" or manifest["seed"] != settings.data.seed:
        raise ContractError("training requires matching seed and a separate development manifest")
    train_entities = {row["entity_id"] for row in read_jsonl(settings.data.manifest.parent / "observations.jsonl")}
    if train_entities & {row["entity_id"] for row in dev_data["observations.jsonl"]}:
        raise ContractError("training/development entity leakage")
    development = gold_requests(dev_data)
    probes = [next(row for row in development if row["target"].action == action) for action in ("create", "update")]
    import torch
    torch.manual_seed(settings.seed)
    runtime = HuggingFaceRuntime(settings.model)
    encoded = [completion_example(runtime.tokenizer, row["request"], row["target"],
               max_sequence=min(settings.max_sequence, settings.generation.max_input_tokens)) for row in corpus]
    for row, tokens in zip(corpus, encoded, strict=True):
        prepared = runtime.prepare(render_request(row["request"]))
        prompt_length = sum(label == -100 for label in tokens["labels"])
        if prepared.payload["input_ids"][0].tolist() != tokens["input_ids"][:prompt_length]:
            raise ContractError("training mask prefix differs from inference prompt token IDs")
    if any(sum(label != -100 for label in row["labels"]) > settings.generation.max_new_tokens for row in encoded):
        raise ContractError("training completion exceeds the matched generation budget")
    for row in probes:
        if runtime.prepare(render_request(row["request"])).token_count > settings.generation.max_input_tokens:
            raise ContractError("CONTEXT_LIMIT: development reload probe exceeds input budget")
    runtime.model = configure_lora(runtime.model, settings)
    before_base = parameter_digest(runtime.model, adapter=False)
    before_adapter = parameter_digest(runtime.model, adapter=True)
    trainable = {name: p.numel() for name, p in runtime.model.named_parameters() if p.requires_grad}
    prepare_output(settings.output_dir)
    write_json(settings.output_dir / "resolved-config.json", json.loads(canonical_json(settings)))
    write_jsonl(settings.output_dir / "corpus.jsonl", [{"request": asdict(row["request"]), "target": asdict(row["target"]),
                "prompt_sha256": digest(render_request(row["request"])), "tokens": tokens} for row, tokens in zip(corpus, encoded, strict=True)])
    started = time.perf_counter()
    initial_loss = mean_completion_loss(runtime.model, encoded, torch, settings.model.device)
    losses = optimize(runtime.model, encoded, settings, torch, log_path=settings.output_dir / "training-log.jsonl")
    final_loss = mean_completion_loss(runtime.model, encoded, torch, settings.model.device)
    base_unchanged = before_base == parameter_digest(runtime.model, adapter=False)
    adapter_changed = before_adapter != parameter_digest(runtime.model, adapter=True)
    if not base_unchanged or not adapter_changed:
        raise CorrectnessError("adapter optimization did not preserve the base and change adapter weights")
    checkpoint = settings.output_dir / "adapter"
    runtime.model.save_pretrained(checkpoint, safe_serialization=True)
    saved_outputs = [runtime.generate(runtime.prepare(render_request(row["request"])), settings.generation) for row in probes]
    training_outputs = []
    for row, tokens in zip(corpus, encoded, strict=True):
        output = runtime.generate(runtime.prepare(render_request(row["request"])), settings.generation)
        target_ids = tuple(label for label in tokens["labels"] if label != -100)
        try:
            proposal = parse_proposal(json.loads(output.text, object_pairs_hook=_unique_object))
        except (ValueError, TypeError, ContractError):
            proposal = None
        training_outputs.append({"observation_id": row["request"].observation.observation_id,
                                 "raw_output": output.text, "token_ids": output.token_ids,
                                 "target_token_ids": target_ids, "target_exact": output.token_ids == target_ids,
                                 "schema_valid": proposal is not None,
                                 "validation_codes": validate(row["request"], proposal) if proposal else None})
    write_jsonl(settings.output_dir / "training-greedy.jsonl", training_outputs)
    from peft import PeftModel
    reloaded = HuggingFaceRuntime(settings.model)
    reloaded.model = PeftModel.from_pretrained(reloaded.model, checkpoint, is_trainable=False, local_files_only=True).eval()
    reloaded_outputs = [reloaded.generate(reloaded.prepare(render_request(row["request"])), settings.generation) for row in probes]
    reload_rows = [{"request": asdict(row["request"]), "before_text": before.text, "after_text": after.text,
                    "before_token_ids": before.token_ids, "after_token_ids": after.token_ids,
                    "match": before.token_ids == after.token_ids} for row, before, after in zip(probes, saved_outputs, reloaded_outputs, strict=True)]
    reload_match = all(row["match"] for row in reload_rows)
    write_jsonl(settings.output_dir / "reload-proof.jsonl", reload_rows)
    adapter_files = {str(p.relative_to(settings.output_dir)): hashlib.sha256(p.read_bytes()).hexdigest()
                     for p in sorted(checkpoint.iterdir()) if p.name in ("adapter_config.json", "adapter_model.safetensors")}
    result = {"schema_version": 1, "status": "trained" if reload_match else "reload_failed", "gate": settings.gate,
              **run_environment(), "model": {**runtime.metadata, **asdict(settings.model), "tokenizer_revision": settings.model.revision,
                                             "adapter_status": "trained_educational" if reload_match else "reload_failed"},
              "dataset": manifest, "development_dataset": dev_manifest, "config_sha256": digest(settings),
              "corpus_sha256": hashlib.sha256((settings.output_dir / "corpus.jsonl").read_bytes()).hexdigest(),
              "adapter_files": adapter_files, "seed": settings.seed, "examples": len(corpus),
              "action_support": dict(Counter(row["target"].action for row in corpus)),
              "trainable_parameters": sum(trainable.values()), "trainable_parameter_names": trainable,
              "total_parameters": sum(p.numel() for p in runtime.model.parameters()),
              "verification": {"base_unchanged": base_unchanged, "adapter_changed": adapter_changed, "reload_match": reload_match},
              "base_parameter_sha256": before_base, "initial_adapter_parameter_sha256": before_adapter,
              "final_adapter_parameter_sha256": parameter_digest(runtime.model, adapter=True),
              "initial_completion_loss": initial_loss, "final_completion_loss": final_loss, "epochs": losses,
              "optimizer": {"kind": "AdamW", "weight_decay": 0.0, "gradient_clip_norm": 1.0,
                            "loss_reduction": "mean per example; remainder accumulation window normalized by actual example count"},
              "checkpoint_selection": "final bounded smoke state; no research selection",
              "overfit_exact": sum(row["target_exact"] for row in training_outputs),
              "overfit_total": len(training_outputs), "overfit_achieved": all(row["target_exact"] for row in training_outputs),
              "training_schema_valid": sum(row["schema_valid"] for row in training_outputs),
              "wall_seconds_excluding_model_load": time.perf_counter() - started,
              "peak_process_memory_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if platform.system() == "Darwin" else 1024),
              "packages": {name: importlib.metadata.version(name) for name in ("torch", "transformers", "peft", "huggingface-hub")},
              "human_reviewers": 0, "torch_cpu_threads": torch.get_num_threads(),
              "purpose": "educational structured-rule imitation; no learned-memory advantage claim"}
    write_json(settings.output_dir / "manifest.json", result)
    if not reload_match:
        raise CorrectnessError("saved adapter did not reproduce exact development token IDs after reload")
    return TrainingManifest(settings.output_dir, result)


def train_adapter(settings: TrainConfig) -> TrainingManifest:
    try:
        return _train_adapter(settings)
    except (RuntimeUnavailable, CorrectnessError):
        raise
    except (ImportError, RuntimeError) as error:
        raise RuntimeUnavailable(f"educational training runtime unavailable: {error}") from error


def from_eval_config(config):
    if config.training.get("gate", "training_not_justified") == "training_not_justified":
        raise RuntimeUnavailable("training gate is training_not_justified; no optimization performed")
    model = ModelConfig(**{key: value for key, value in config.proposer.items() if key != "kind"})
    return TrainConfig(config.data, config.output_dir, model, generation=GenerationConfig(**config.generation), **config.training)
