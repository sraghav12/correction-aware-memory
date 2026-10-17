"""Optional cached model inference."""

from dataclasses import asdict, dataclass
import importlib.metadata
import json
import re
import time

from cam.contracts import ContractError, DecisionRequest, Proposal, RuntimeUnavailable, digest, parse_proposal
from cam.prompts import render_request


@dataclass(frozen=True)
class ModelConfig:
    revision: str
    model_id: str = "Qwen/Qwen3-0.6B"
    device: str = "cpu"
    adapter_path: str | None = None

    def __post_init__(self):
        if self.model_id != "Qwen/Qwen3-0.6B" or not isinstance(self.revision, str) or not re.fullmatch(r"[0-9a-f]{40}", self.revision):
            raise ContractError("Qwen3-0.6B requires a pinned 40-hex model/tokenizer revision")
        if self.device not in ("cpu", "mps"):
            raise ContractError("device must be cpu or mps; there is no automatic fallback")
        if self.adapter_path is not None:
            raise ContractError("adapter loading awaits the training task")


@dataclass(frozen=True)
class GenerationConfig:
    max_input_tokens: int = 2048
    max_new_tokens: int = 256
    enable_thinking: bool = False
    do_sample: bool = False
    decoding: str = "unconstrained"

    def __post_init__(self):
        if type(self.max_input_tokens) is not int or not 1 <= self.max_input_tokens <= 2048:
            raise ContractError("max_input_tokens must be in 1..2048")
        if type(self.max_new_tokens) is not int or not 1 <= self.max_new_tokens <= 256:
            raise ContractError("max_new_tokens must be in 1..256")
        if self.enable_thinking is not False or self.do_sample is not False or self.decoding != "unconstrained":
            raise ContractError("only deterministic, nonthinking, unconstrained decoding is implemented")


@dataclass(frozen=True)
class PreparedInput:
    payload: object
    token_count: int


@dataclass(frozen=True)
class GenerationOutput:
    text: str
    output_tokens: int


class ModelOutputError(ContractError):
    def __init__(self, code, detail, raw_output=None):
        super().__init__(f"{code}: {detail}")
        self.code, self.raw_output = code, raw_output


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


class ModelProposer:
    def __init__(self, config: ModelConfig, generation: GenerationConfig | None = None, *, runtime=None):
        self.config = config
        self.generation = generation or GenerationConfig()
        self.runtime = runtime if runtime is not None else HuggingFaceRuntime(config)
        self.last_metadata = {}

    @property
    def metadata(self):
        return {**self.runtime.metadata, **asdict(self.config), "tokenizer_revision": self.config.revision,
                "generation": asdict(self.generation)}

    def propose(self, request: DecisionRequest) -> Proposal:
        self.last_metadata = {"revision": self.config.revision, "raw_output": None, "failure_code": None}
        started = time.perf_counter()
        try:
            messages = render_request(request)
            self.last_metadata["prompt_sha256"] = digest(messages)
            prepared = self.runtime.prepare(messages)
            self.last_metadata["input_tokens"] = prepared.token_count
            if prepared.token_count > self.generation.max_input_tokens:
                raise ModelOutputError("CONTEXT_LIMIT", f"{prepared.token_count} input tokens exceed {self.generation.max_input_tokens}")
            output = self.runtime.generate(prepared, self.generation)
            self.last_metadata.update(raw_output=output.text, output_tokens=output.output_tokens)
            if output.output_tokens > self.generation.max_new_tokens:
                raise ModelOutputError("OUTPUT_LIMIT", "runtime exceeded generation budget", output.text)
            try:
                return parse_proposal(json.loads(output.text, object_pairs_hook=_unique_object))
            except (ValueError, TypeError, ContractError) as error:
                raise ModelOutputError("MODEL_OUTPUT", str(error), output.text) from error
        except ContractError as error:
            self.last_metadata["failure_code"] = getattr(error, "code", str(error).split(":", 1)[0])
            raise
        finally:
            self.last_metadata["latency_seconds"] = time.perf_counter() - started

    __call__ = propose


def from_eval_config(config):
    settings = {key: value for key, value in config.proposer.items() if key != "kind"}
    return ModelProposer(ModelConfig(**settings), GenerationConfig(**config.generation))


class HuggingFaceRuntime:
    """No network permission is implied by selecting a model. All loads are local."""

    def __init__(self, config: ModelConfig):
        started = time.perf_counter()
        try:
            from huggingface_hub import snapshot_download
        except ImportError as error:
            raise RuntimeUnavailable("optional ML dependencies absent; install the locked ml extra before a cached model run") from error
        try:
            snapshot = snapshot_download(config.model_id, revision=config.revision, local_files_only=True)
        except OSError as error:
            raise RuntimeUnavailable("pinned model is not cached; no download attempted") from error
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
            if config.device == "mps" and not torch.backends.mps.is_available():
                raise RuntimeUnavailable("requested MPS backend is unavailable; choose cpu explicitly")
            self.torch, self.device = torch, config.device
            self.tokenizer = AutoTokenizer.from_pretrained(snapshot, local_files_only=True, trust_remote_code=False)
            self.model = AutoModelForCausalLM.from_pretrained(snapshot, local_files_only=True,
                        trust_remote_code=False, use_safetensors=True, dtype=torch.float32).to(config.device)
            self.model.eval()
        except (ImportError, OSError, RuntimeError, ValueError) as error:
            raise RuntimeUnavailable(f"cached model runtime unavailable: {error}") from error
        self.metadata = {"backend": config.device, "dtype": "float32", "real_model": True,
                         "load_seconds": time.perf_counter() - started,
                         "packages": {name: importlib.metadata.version(name) for name in ("torch", "transformers", "huggingface-hub")}}

    def prepare(self, messages):
        encoded = self.tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True,
                    enable_thinking=False, return_dict=True, return_tensors="pt", truncation=False)
        return PreparedInput(encoded, encoded["input_ids"].shape[-1])

    def generate(self, prepared, generation):
        encoded = {name: value.to(self.device) for name, value in prepared.payload.items()}
        try:
            with self.torch.inference_mode():
                output = self.model.generate(**encoded, max_new_tokens=generation.max_new_tokens, do_sample=False,
                            temperature=None, top_p=None, top_k=None, num_beams=1,
                            pad_token_id=self.tokenizer.eos_token_id, use_cache=True)
            tokens = output[0, prepared.token_count:]
            return GenerationOutput(self.tokenizer.decode(tokens, skip_special_tokens=True), len(tokens))
        except RuntimeError as error:
            raise RuntimeUnavailable(f"generation failed on requested {self.device} backend: {error}") from error

    def probe_backward(self):
        """Tiny compatibility check; no optimizer, updates, saved weights, or training claim."""
        started = time.perf_counter()
        result = {"status": "failed", "weights_updated": False, "tokens": 4}
        try:
            self.model.train()
            encoded = self.tokenizer("Memory preserves facts.", return_tensors="pt")
            tokens = encoded["input_ids"][:, :4].to(self.device)
            loss = self.model(input_ids=tokens, labels=tokens, use_cache=False).loss
            loss.backward()
            grads = [p.grad for p in self.model.parameters() if p.grad is not None]
            finite_loss = bool(self.torch.isfinite(loss).item())
            finite = finite_loss and bool(grads) and all(bool(self.torch.isfinite(g).all().item()) for g in grads)
            result.update(status="passed" if finite else "failed", loss=float(loss.detach().cpu()) if finite_loss else None, finite_gradients=finite,
                          tokens=tokens.shape[-1])
        except RuntimeError as error:
            result["error"] = str(error)
        finally:
            self.model.zero_grad(set_to_none=True)
            self.model.eval()
        result["seconds"] = time.perf_counter() - started
        return result
