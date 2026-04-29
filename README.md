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

PersistentPoker-Bench is an open-source benchmark for evaluating advanced LLM reasoning, memory, and strategic decision-making in a custom multiplayer No-Limit Texas Hold'em environment.

The benchmark combines:

- A custom hand evaluator with duplicate-aware categories
- A persistent public pool that compounds across hands
- A memory verification step for model state tracking
- A deterministic-seed tournament runner with public metrics and dual leaderboards

## Status

Current milestone: Phase 4 pre-release workflow.

The official v1 rules and project architecture live in:

- `docs/rules_v1_option_a.md`
- `docs/architecture.md`
- `docs/tos_safety.md`

## Core Benchmark Properties

- Game: No-Limit Texas Hold'em
- Players: 4 by default, configurable from 3 to 6
- Betting: full no-limit, including all-in and side pots
- Shared state: persistent public pool carried across hands
- Memory check: explicit `believed_pool` verification step
- Default winner action: continue the pool unless reset is chosen
- Reproducibility: deterministic seeded hand generation
- Official tracks: `frontier` and `efficiency`

## Roadmap

1. Phase 0 - finalized rules, model registry, architecture, packaging
2. Phase 1 - core game engine and hand evaluator
3. Phase 2 - LLM integration through LiteLLM with strict JSON outputs
4. Phase 3 - tournament orchestration and metrics
5. Phase 4 - public release assets and demo
6. Phase 5 - variants and future rule versions

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

Run a deterministic local demo with static agents:

```bash
persistentpoker-bench demo \
  --track frontier \
  --hands 2 \
  --seeds 20260428,20260429 \
  --outdir ./artifacts/demo-frontier
```

This writes:

- `results.jsonl`
- `match_summaries.jsonl`
- `decision_traces.jsonl`
- `leaderboard.csv`
- `run_summary.json`

Play a live terminal session with one or more humans:

```bash
persistentpoker-bench play \
  --players "Alice,Bob,CPU1,CPU2" \
  --human-seats 1,2 \
  --hands 3 \
  --seed 20260428
```

Notes:

- `--human-seats` uses 1-based seat indices
- non-human seats currently use deterministic passive bots
- the live renderer shows public state continuously and reveals human hole cards during play
- tied administrative decisions now use deterministic `d6` roll tie-breaks

Play a mixed human + LiteLLM table from config and write a structured replay:

```bash
persistentpoker-bench play \
  --config ./configs/play_mixed.json
```

Example mixed play config:

```json
{
  "seed": 20260428,
  "hand_count": 2,
  "replay_out": "./artifacts/play_mixed_replay.json",
  "players": [
    {
      "name": "Alice",
      "kind": "human"
    },
    {
      "name": "GPT-5.5",
      "kind": "litellm",
      "provider": "openai",
      "model_id": "gpt-5.5",
      "temperature": 0.0,
      "max_tokens": 300
    },
    {
      "name": "DeepSeek",
      "kind": "litellm",
      "provider": "deepseek",
      "model_id": "deepseek-v4-pro",
      "temperature": 0.0,
      "max_tokens": 300
    },
    {
      "name": "CPU1",
      "kind": "passive_bot"
    }
  ]
}
```

Launch the replay web studio:

```bash
persistentpoker-bench web --host 127.0.0.1 --port 7860
```

Ready-to-use configs:

- [configs/play_mixed.json](/Users/robertbadinter/Desktop/Poker-Bench/configs/play_mixed.json)
- [configs/frontier_live.json](/Users/robertbadinter/Desktop/Poker-Bench/configs/frontier_live.json)

Hugging Face Space readiness:

- Space app entrypoint: [hf_space/app.py](/Users/robertbadinter/Desktop/Poker-Bench/hf_space/app.py)
- Space dependencies: [requirements.txt](/Users/robertbadinter/Desktop/Poker-Bench/requirements.txt)
- Space metadata: this root [README.md](/Users/robertbadinter/Desktop/Poker-Bench/README.md) already includes the YAML header expected by Hugging Face Spaces
- provider keys should be stored as **Space Secrets**, not hard-coded
- exact deployment guide: [docs/hf_space_deploy.md](/Users/robertbadinter/Desktop/Poker-Bench/docs/hf_space_deploy.md)

Run a live LiteLLM-backed tournament from JSON config:

```bash
persistentpoker-bench run \
  --config ./configs/frontier_live.json \
  --outdir ./artifacts/frontier-live
```

Example config:

```json
{
  "track": "frontier",
  "seeds": [20260428, 20260429],
  "hand_count": 2,
  "base_seed": 0,
  "initial_button_index": 0,
  "budget_caps": {
    "total_cost_cap": 5.0,
    "per_provider_cap": {
      "openai": 2.0
    },
    "per_model_cap": {
      "gpt-5.5": 2.0
    }
  },
  "lineups": [
    {
      "lineup_id": "frontier-main",
      "entrants": [
        {
          "seat_name": "P1",
          "provider": "deepseek",
          "model_id": "deepseek-v4-pro"
        },
        {
          "seat_name": "P2",
          "provider": "xai",
          "model_id": "grok-4.20-reasoning"
        },
        {
          "seat_name": "P3",
          "provider": "gemini",
          "model_id": "gemini-3.1-pro-preview"
        },
        {
          "seat_name": "P4",
          "provider": "openai",
          "model_id": "gpt-5.5"
        }
      ]
    }
  ]
}
```

## Release Artifacts

The public workflow now supports:

- deterministic seed-based replays
- structured replay JSON for local play sessions
- dual leaderboards: `frontier` and `efficiency`
- JSONL exports for full results, summaries, and decision traces
- CSV leaderboard export
- budget caps per run, provider, and model
- LiteLLM multi-provider execution
- live terminal visualization
- mixed human/bot/LiteLLM participation
- Gradio replay UI
- live web table with action sidebar and structured replay updates

## Repository Layout

```text
docs/
  architecture.md
  rules_v1_option_a.md
  tos_safety.md
src/persistentpoker_bench/
  __init__.py
  models.py
  spec.py
tests/
  test_spec.py
```

## License

TBD during Phase 4. MIT or Apache-2.0 are both compatible candidates.
