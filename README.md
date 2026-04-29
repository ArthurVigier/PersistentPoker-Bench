---
title: PersistentPoker-Bench
emoji: "🂡"
colorFrom: green
colorTo: yellow
sdk: gradio
sdk_version: 5.49.1
app_file: hf_space/app.py
pinned: false
---

# PersistentPoker-Bench

PersistentPoker-Bench is an open-source benchmark for evaluating advanced LLM reasoning, memory, and strategic decision-making in a custom multiplayer No-Limit environment.

The benchmark combines:

- A custom hand evaluator with duplicate-aware categories
- A persistent public pool that compounds across hands
- A memory verification step for model state tracking
- A deterministic-seed tournament runner with public metrics and dual leaderboards
- **V2 H.O.R.S.E. Engine**: Dynamic game rule rotation (Hold'em, Omaha 8B, Razz, Stud, Stud 8B)
- **Survival Mode**: Endless endurance runs ending only upon bankruptcy

## Status

Current milestone: Phase 5 (H.O.R.S.E Variant & Agentic Resilience).

The official rules and project architecture live in:

- `docs/rules_v1_option_a.md`
- `docs/architecture.md`
- `docs/tos_safety.md`

## Core Benchmark Properties

- Game Modes: `holdem` (V1) or `horse_v2` (V2)
- Players: 4 by default, configurable from 3 to 6
- Betting: full no-limit, including all-in and side pots
- Shared state: persistent public pool carried across hands (board cards + stud up-cards)
- Memory check: explicit `believed_pool` verification step
- Metacognition: Default winner action is `continue`, but models can tactically choose `reset`
- Official tracks: `frontier` and `efficiency`
- Resilience: Relaxed JSON parsing mode for ultra-verbose "Reasoning" models

## Supported Flagship Models (April 2026 Roster)

- **Gemini 3.1 Pro** & **Gemini 3 Flash** (Google)
- **GPT-5.5** & **GPT-5.4 Mini** (OpenAI)
- **Grok 4.20 Reasoning** & **Grok 4.1 Fast** (xAI)
- **Mistral Large latest** & **Mistral Small 4** (Mistral AI)
- **DeepSeek V4 Pro** (DeepSeek)

## Roadmap

1. Phase 0 - finalized rules, model registry, architecture, packaging
2. Phase 1 - core game engine and hand evaluator
3. Phase 2 - LLM integration through LiteLLM with strict JSON outputs
4. Phase 3 - tournament orchestration and metrics
5. Phase 4 - public release assets and demo
6. **Phase 5 (Active) - H.O.R.S.E variants, incremental JSONL writing, and Diabolical Survival Mode**

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev,llm,ui]'
pytest
```

## CLI Workflow

List the official benchmark roster:

```bash
persistentpoker-bench models
persistentpoker-bench models --track frontier
```

Run a live LiteLLM-backed tournament from JSON config (Incremental writing supported):

```bash
persistentpoker-bench run \
  --config ./configs/horse_v2_frontier_mistral_2026-04-29.json \
  --outdir ./artifacts/horse-v2-run
```

### V2 H.O.R.S.E Config Example (with relaxed parsing)

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

*Note: For Deep Reasoning models (GPT-5.5, Mistral Large, Grok 4.20), `prefer_json_mode: false` is highly recommended to prevent API crashes when the model outputs `<think>` blocks or verbose markdown.*

Play a live terminal session with one or more humans:

```bash
persistentpoker-bench play \
  --players "Alice,Bob,CPU1,CPU2" \
  --human-seats 1,2 \
  --hands 3 \
  --seed 20260428
```

Launch the replay web studio (Gradio):

```bash
persistentpoker-bench web --host 127.0.0.1 --port 7860
```

Hugging Face Space readiness:

- Space app entrypoint: `hf_space/app.py`
- Space dependencies: `requirements.txt`
- provider keys should be stored as **Space Secrets**, not hard-coded

## Release Artifacts

The public workflow now supports:

- **Resilient Incremental Logging**: `results.jsonl`, `match_summaries.jsonl`, `decision_traces.jsonl` are written match-by-match to prevent data loss on API timeout.
- CSV leaderboard export focusing on ROI and Chip Deltas
- budget caps per run, provider, and model
- LiteLLM multi-provider execution with exponential backoff retries
- Gradio replay UI with real-time markdown extraction

## License

TBD. MIT or Apache-2.0 are both compatible candidates.
