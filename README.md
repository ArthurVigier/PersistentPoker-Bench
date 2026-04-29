---
title: PersistentPoker-Bench
emoji: "🃏"
colorFrom: green
colorTo: yellow
sdk: gradio
sdk_version: 5.49.1
app_file: hf_space/app.py
pinned: false
---

# PersistentPoker-Bench

PersistentPoker-Bench is an open benchmark for evaluating LLM agents in a
path-dependent multiplayer poker environment. It stress-tests strategic
reasoning, public-state memory, strict JSON compliance, cost-aware inference,
and long-horizon robustness under a custom persistent-card pool.

- Interactive Replay Studio: [Hugging Face Space](https://huggingface.co/spaces/Artvv/PersistentPoker-Bench)
- Official Evaluation Logs: [Hugging Face Dataset](https://huggingface.co/datasets/Artvv/PersistentPoker-Bench-Data)

## What It Tests

The benchmark combines ordinary poker pressure with agentic failure modes:

- **Persistent public memory**: exposed cards accumulate across hands unless a winner chooses to reset the pool.
- **Audited belief tracking**: every model must report `believed_pool`, preserving duplicate cards.
- **Strict protocol reliability**: decisions must be valid JSON and legal poker actions.
- **State governance**: winners choose whether the next hand inherits or clears the public pool.
- **Variant switching**: H.O.R.S.E. mode rotates Hold'em, Omaha 8B, Razz, Stud, and Stud 8B.
- **Resource awareness**: metrics track tokens, estimated cost, parsing success, memory accuracy, chips, and survival.
- **Replayability**: seeded tournaments produce JSONL artifacts, visual replays, and video renders.

## Key Findings

April 2026 frontier and efficiency runs surfaced several architectural lessons:

- **Reasoning can fight compliance**: stronger reasoning models may still lose benchmark value if verbose outputs break strict JSON.
- **Reset is metacognition**: clearing the pool can be correct when public history becomes cognitively toxic.
- **Rule switching is a real skill**: H.O.R.S.E. exposes catastrophic rule drift between highball, lowball, and stud-like regimes.
- **ROI can beat win rate**: a model can win many hands while losing stack EV through passive calling or poor risk control.

## Current Capabilities

- Game modes: `holdem` and `horse_v2`
- Players: configurable from 3 to 6
- Betting: no-limit actions, all-in handling, and side pots
- Tracks: `frontier` and `efficiency`
- Termination: fixed hand limit, first-bankrupt survival, and marathon-style configs
- Runtimes: LiteLLM providers plus local open-source backends through `local_backend`
- Visualization: Gradio replay studio and MP4 video renderer

## Documentation

Core project documents:

- `docs/rules_v1_option_a.md`
- `docs/horse_v2_topological_rules.md`
- `docs/current_game_theoretic_framework.md`
- `docs/local_open_models.md`
- `docs/architecture.md`
- `docs/tos_safety.md`

## Model Roster

The packaged registry includes frontier and efficiency entrants from OpenAI,
xAI, Google/Gemini, Mistral, DeepSeek, and Qwen. Custom API, OpenRouter, and
local open-source entrants can be supplied directly in JSON configs.

## Roadmap

1. Phase 0 - finalized rules, model registry, architecture, packaging
2. Phase 1 - core game engine and hand evaluator
3. Phase 2 - LLM integration through LiteLLM with strict JSON outputs
4. Phase 3 - tournament orchestration and metrics
5. Phase 4 - public release assets and demo
6. Phase 5 - H.O.R.S.E variants, replay/video tooling, local model runtimes, and survival modes

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev,llm,ui]'
pytest
```

## Common Workflows

List benchmark models:

```bash
persistentpoker-bench models
persistentpoker-bench models --track frontier
```

Run a LiteLLM/API-backed tournament:

```bash
persistentpoker-bench run \
  --config ./configs/horse_v2_frontier_mistral_2026-04-29.json \
  --outdir ./artifacts/horse-v2-run
```

Run a local open-source model through Ollama, vLLM, llama.cpp, or another
OpenAI-compatible local server:

```bash
persistentpoker-bench run \
  --config ./configs/local/qwen3_ollama_smoke.json \
  --outdir ./artifacts/local-qwen3-smoke
```

Launch the replay studio:

```bash
persistentpoker-bench web --host 127.0.0.1 --port 7860
```

Render a benchmark video:

```bash
persistentpoker-bench video \
  --input ./artifacts/openai-xai-frontier-calibrated-2026-04-29/run_summary.json \
  --output ./artifacts/openai-xai-frontier-calibrated-2026-04-29/frontier.mp4 \
  --fps 2
```

Play a terminal session with humans and bots:

```bash
persistentpoker-bench play \
  --players "Alice,Bob,CPU1,CPU2" \
  --human-seats 1,2 \
  --hands 3 \
  --seed 20260428
```

## Tournament Config Example

H.O.R.S.E. config with relaxed parsing for verbose reasoning models:

```json
{
  "track": "frontier",
  "game_mode": "horse_v2",
  "termination_rule": "hand_limit",
  "seeds": [20260429],
  "hand_count": 5,
  "base_seed": 0,
  "budget_caps": {
    "total_cost_cap": 25.0
  },
  "lineups": [
    {
      "lineup_id": "horse-v2-frontier",
      "entrants": [
        {
          "seat_name": "Mistral Large",
          "provider": "mistral",
          "model_id": "mistral-large-latest",
          "prefer_json_mode": false
        },
        {
          "seat_name": "Gemini 3.1 Pro",
          "provider": "gemini",
          "model_id": "gemini-3.1-pro",
          "extra_kwargs": {
            "thinking": { "type": "enabled", "budget_tokens": 256 }
          }
        }
      ]
    }
  ]
}
```

For deep-reasoning models, `prefer_json_mode: false` can be useful when a
provider rejects JSON mode or the model emits verbose hidden-reasoning style
content. The parser still normalizes the final decision into the benchmark
schema.

Local model entrants use the same schema with an additional `local_backend`:

```json
{
  "seat_name": "Qwen Local",
  "provider": "local",
  "model_id": "Qwen/Qwen3-8B-GGUF-Q4",
  "display_name": "Qwen3 8B Ollama Q4",
  "local_backend": "ollama",
  "local_model": "qwen3:8b",
  "base_url": "http://127.0.0.1:11434",
  "metadata": {
    "parameter_count": "8B",
    "architecture": "dense_transformer",
    "quantization": "q4",
    "context_length": 32768
  }
}
```

## Artifacts

Runs can emit:

- `results.jsonl`
- `match_summaries.jsonl`
- `decision_traces.jsonl`
- `leaderboard.csv`
- `run_summary.json`
- replay JSON files
- MP4 video renders

Decision traces include normalized actions, raw model text, parse mode,
reported pool belief, memory scores, usage summaries, and local model metadata
when available.

## Hugging Face Space

- Space entrypoint: `hf_space/app.py`
- Space dependencies: `requirements.txt`
- Provider keys should be stored as Space Secrets, not hard-coded.

## License

TBD. MIT or Apache-2.0 are both compatible candidates.
