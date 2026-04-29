from __future__ import annotations

from persistentpoker_bench.local_models.base import LocalModelBackend
from persistentpoker_bench.local_models.llama_cpp_adapter import LlamaCppBackend
from persistentpoker_bench.local_models.ollama_adapter import OllamaBackend
from persistentpoker_bench.local_models.openai_compatible import OpenAICompatibleBackend
from persistentpoker_bench.local_models.transformers_adapter import TransformersBackend
from persistentpoker_bench.local_models.vllm_adapter import VLLMBackend


def create_local_backend(name: str) -> LocalModelBackend:
    normalized = name.strip().lower().replace("-", "_")
    if normalized in {"openai_compatible", "openai", "local_openai"}:
        return OpenAICompatibleBackend()
    if normalized == "vllm":
        return VLLMBackend()
    if normalized in {"llama_cpp", "llamacpp", "llama.cpp"}:
        return LlamaCppBackend()
    if normalized == "ollama":
        return OllamaBackend()
    if normalized in {"transformers", "hf_transformers"}:
        return TransformersBackend()
    raise ValueError(
        "Unsupported local_backend. Expected one of: "
        "openai_compatible, vllm, llama_cpp, ollama, transformers."
    )
