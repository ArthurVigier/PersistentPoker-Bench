from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import Any

from persistentpoker_bench.local_models.base import LocalModelConfig, LocalModelResponse
from persistentpoker_bench.prompting import PromptBundle


@dataclass(frozen=True, slots=True)
class TransformersBackend:
    """Optional direct Transformers backend for small local experiments.

    Production-scale local runs should usually prefer vLLM, llama.cpp server,
    SGLang, TGI, or Ollama so inference stays isolated from the benchmark
    process.
    """

    def complete(
        self,
        *,
        prompt_bundle: PromptBundle,
        config: LocalModelConfig,
    ) -> LocalModelResponse:
        transformers = _load_transformers()
        tokenizer = transformers.AutoTokenizer.from_pretrained(
            config.model,
            **dict(config.extra_kwargs.get("tokenizer_kwargs", {})),
        )
        model = transformers.AutoModelForCausalLM.from_pretrained(
            config.model,
            **dict(config.extra_kwargs.get("model_kwargs", {})),
        )
        prompt = tokenizer.apply_chat_template(
            prompt_bundle.messages,
            tokenize=False,
            add_generation_prompt=True,
        )
        inputs = tokenizer(prompt, return_tensors="pt")
        generation_kwargs: dict[str, Any] = {
            "max_new_tokens": config.max_tokens,
            "do_sample": config.temperature is not None and config.temperature > 0,
        }
        if config.temperature is not None and config.temperature > 0:
            generation_kwargs["temperature"] = config.temperature
        output = model.generate(**inputs, **generation_kwargs)
        generated = output[0][inputs["input_ids"].shape[-1] :]
        text = tokenizer.decode(generated, skip_special_tokens=True)
        return LocalModelResponse(
            content=text.strip(),
            usage={
                "prompt_tokens": int(inputs["input_ids"].shape[-1]),
                "completion_tokens": int(generated.shape[-1]),
            },
            raw_response=None,
        )


def _load_transformers() -> Any:
    try:
        return import_module("transformers")
    except ImportError as exc:
        raise ImportError(
            "transformers is not installed. Install it separately for direct local inference, "
            "or use a local HTTP backend such as vLLM, llama.cpp, or Ollama."
        ) from exc
