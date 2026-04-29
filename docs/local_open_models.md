# Local Open-Source Model Evaluation

PersistentPoker-Bench can run local open-source models without changing the
game engine. Local models are treated as inference backends that emit the same
decision JSON as API-backed models.

The design goal is to separate:

```text
model weights + inference runtime + agent scaffold = benchmark behavior
```

This makes local runs useful for architecture research: dense versus MoE,
parameter count, quantization, context length, constrained decoding, memory
scaffolds, and backend differences can all be recorded and compared.

## Supported Backends

The current local backend layer supports:

| `local_backend` | Default endpoint | Notes |
|---|---|---|
| `vllm` | `http://127.0.0.1:8000/v1` | OpenAI-compatible server |
| `llama_cpp` | `http://127.0.0.1:8080/v1` | `llama.cpp` OpenAI-compatible server |
| `openai_compatible` | `http://127.0.0.1:8000/v1` | Generic OpenAI-compatible local endpoint |
| `ollama` | `http://127.0.0.1:11434` | Native Ollama `/api/chat` endpoint |
| `transformers` | in-process | Optional, mostly for small experiments |

For rigorous benchmark runs, prefer an HTTP runtime such as vLLM, llama.cpp,
SGLang/TGI in OpenAI-compatible mode, or Ollama. Keeping inference outside the
benchmark process makes crashes, GPU memory pressure, and dependency conflicts
much easier to isolate.

## Config Shape

A local entrant is selected with `local_backend`:

```json
{
  "seat_name": "Qwen 32B Local",
  "provider": "local",
  "model_id": "Qwen/Qwen3-32B",
  "display_name": "Qwen3 32B local BF16",
  "local_backend": "vllm",
  "base_url": "http://127.0.0.1:8000/v1",
  "temperature": 0.0,
  "max_tokens": 400,
  "prefer_json_mode": true,
  "metadata": {
    "parameter_count": "32B",
    "architecture": "dense_transformer",
    "quantization": "bf16",
    "context_length": 32768,
    "constrained_decoding": false,
    "memory_scaffold": "none"
  }
}
```

The `model_id` is the research identity used in artifacts and leaderboards.
If the runtime expects a different model name, set `local_model`.

```json
{
  "model_id": "Qwen/Qwen3-8B-GGUF-Q4_K_M",
  "local_model": "qwen3:8b",
  "local_backend": "ollama"
}
```

## Example Commands

Start vLLM:

```bash
vllm serve Qwen/Qwen3-32B --host 127.0.0.1 --port 8000
```

Run a local benchmark config:

```bash
persistentpoker-bench run \
  --config ./configs/local/qwen3_ollama_smoke.json \
  --outdir ./artifacts/local-qwen3-smoke
```

Render the result:

```bash
persistentpoker-bench video \
  --input ./artifacts/local-qwen3-smoke/run_summary.json \
  --output ./artifacts/local-qwen3-smoke/local-qwen3.mp4
```

## Research Metadata

The `metadata` object is copied into decision-event usage summaries as
`model_metadata`. Use it to preserve the experimental conditions:

```json
{
  "parameter_count": "14B",
  "architecture": "dense_transformer",
  "quantization": "q4_k_m",
  "context_length": 32768,
  "constrained_decoding": true,
  "memory_scaffold": "external-verifier-v1",
  "runtime": "llama.cpp",
  "gpu": "m2-ultra"
}
```

Useful comparison axes:

1. same weights, different quantization;
2. same weights, different backend;
3. same backend, different constrained decoding;
4. same model, with and without memory scaffold;
5. small stable model versus large fragile model;
6. long-context model versus reset-heavy short-context model.

## Non-Invasive Boundary

The local model layer does not change:

1. betting rules;
2. showdown rules;
3. persistent-pool update rules;
4. metrics;
5. leaderboard sorting;
6. replay/video serialization.

It only changes how an agent obtains the JSON decision envelope. That keeps
local-weight research comparable to existing frontier and efficiency runs.
