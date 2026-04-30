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

PersistentPoker-Bench is an open benchmark for evaluating LLM agents in
path-dependent multiplayer poker environments. It stresses strategic reasoning,
public-state memory, strict JSON compliance, cost-aware inference, hidden
information discipline, and long-horizon robustness under custom poker variants.

- Interactive Replay Studio: [Hugging Face Space](https://huggingface.co/spaces/Artvv/PersistentPoker-Bench)
- Official Evaluation Logs: [Hugging Face Dataset](https://huggingface.co/datasets/Artvv/PersistentPoker-Bench-Data)

## What It Tests

- Persistent public memory: exposed cards accumulate across hands unless a winner resets the pool.
- Belief tracking: every model reports `believed_pool`, preserving duplicate cards.
- Protocol reliability: outputs must normalize to valid JSON and legal poker actions.
- State governance: winners choose `reset` or `continue` for the next public pool.
- Variant switching: H.O.R.S.E. rotates Hold'em, Omaha 8B, Razz, Stud, and Stud 8B.
- Market reasoning: V3 adds a Wall Street row of priced public card assets.
- Reproducibility: seeded tournaments emit JSONL artifacts, CSV leaderboards, replay JSON, and videos.

## Game Modes

- `holdem`: baseline persistent-pool Texas Hold'em.
- `horse_v2`: H.O.R.S.E. backbone with persistent pool and configurable rotation.
- `horse_v3_wall_street`: H.O.R.S.E. plus a Wall Street card market before betting actions.

## Repository Layout

- `src/persistentpoker_bench/`: benchmark engine, adapters, CLI, replay, and video renderer.
- `configs/`: runnable tournament configs.
- `docs/`: formal rules, game-theory notes, architecture, local model notes, and V3 design.
- `tests/`: pytest suite for engine, parser, CLI, replay, local models, and V3 market logic.
- `hf_space/`: Hugging Face Space entrypoint.
- `requirements.txt`: reproducible default install for GitHub and Spaces.
- `.env.example`: local environment template with supported provider keys.

## Clean Install

Use Python 3.11 or newer.

```bash
git clone <repo-url>
cd Poker-Bench

python -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
pip install -r requirements.txt
```

Verify the install:

```bash
persistentpoker-bench models
pytest -q
python -m ruff check src tests
```

## Environment

Create a local `.env` from the template:

```bash
cp .env.example .env
```

Fill only the providers you plan to run:

```bash
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
GEMINI_API_KEY=...
MISTRAL_API_KEY=...
XAI_API_KEY=...
DEEPSEEK_API_KEY=...
```

The CLI loads `.env` automatically for `persistentpoker-bench run`. Lowercase
aliases such as `claude_api_key` and `openai_api_key` are also normalized for
convenience, but uppercase names are preferred for reproducibility.

Never commit `.env`. The tracked template is `.env.example`.

## Local No-API Smoke Runs

Baseline demo:

```bash
persistentpoker-bench demo \
  --track frontier \
  --hands 2 \
  --seeds 20260430 \
  --outdir ./artifacts/demo-frontier
```

H.O.R.S.E. V3 Wall Street demo:

```bash
persistentpoker-bench demo \
  --track frontier \
  --hands 2 \
  --seeds 20260430 \
  --game-mode horse_v3_wall_street \
  --horse-hands-per-game 2 \
  --outdir ./artifacts/horse-v3-wall-street-demo
```

These demos use deterministic static agents, so they are safe for CI and do not
consume API credits.

## API-Backed Runs

Classic H.O.R.S.E. V2 frontier run:

```bash
persistentpoker-bench run \
  --config ./configs/horse_v2_frontier_claude_diverse_2026-04-30.json \
  --outdir ./artifacts/horse-v2-frontier-claude-diverse-2026-04-30
```

Wall Street H.O.R.S.E. V3 frontier run:

```bash
persistentpoker-bench run \
  --config ./configs/horse_v3_wall_street_claude_diverse_2026-04-30.json \
  --outdir ./artifacts/horse-v3-wall-street-frontier-2026-04-30
```

Local open-source model smoke run:

```bash
persistentpoker-bench run \
  --config ./configs/local/qwen3_ollama_smoke.json \
  --outdir ./artifacts/local-qwen3-ollama-smoke
```

## V3 Wall Street Decision Schema

V3 keeps the existing betting schema and adds optional market fields. Models may
omit the market action; the engine treats that as `pass_market`.

```json
{
  "market_action": { "type": "buy_card", "slot": 0 },
  "action": "call",
  "amount": null,
  "believed_pool": ["Ah", "Kd"],
  "winner_pool_decision": "continue",
  "reasoning": "The cheap card improves my low draw and denies opponent value."
}
```

The engine records both `executed_market_action` and `executed_action` in the
transcript. Market spend increases the pot without changing the player's current
betting-street obligation, so ordinary `call` and `raise` logic remains stable.

## Replay, Web UI, and Video

Launch the replay studio:

```bash
persistentpoker-bench web --host 127.0.0.1 --port 7860
```

Render a video from a run summary, replay, or JSONL artifact:

```bash
persistentpoker-bench video \
  --input ./artifacts/horse-v3-wall-street-frontier-2026-04-30/run_summary.json \
  --output ./artifacts/horse-v3-wall-street-frontier-2026-04-30/v3.mp4 \
  --fps 2
```

## Output Artifacts

Tournament runs write:

- `results.jsonl`: full serialized match records.
- `match_summaries.jsonl`: compact per-match summaries.
- `decision_traces.jsonl`: per-decision raw output, normalized action, memory score, usage, and market action.
- `leaderboard.csv`: model-level aggregate rows.
- `run_summary.json`: artifact index.

Replay payloads include final stacks, board/up-cards, persistent pool before and
after, transcript events, tiebreak events, and V3 market state when enabled.

## Config Notes

Important top-level config keys:

- `track`: `frontier` or `efficiency`.
- `game_mode`: `holdem`, `horse_v2`, or `horse_v3_wall_street`.
- `seeds`: deterministic match seeds.
- `hand_count`: hands per match.
- `horse_hands_per_game`: number of hands before rotating to the next H.O.R.S.E. variant.
- `budget_caps`: optional cost guardrails.
- `lineups`: model/provider entrants.

V3-specific keys:

```json
{
  "wall_street_slots": 4,
  "wall_street_price_multipliers": [1, 2, 3, 4],
  "allow_market_all_in": false
}
```

## Local Model Backends

Configs can target local models by adding `local_backend`:

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

Supported local backend names:

- `ollama`
- `vllm`
- `llama_cpp`
- `openai_compatible`
- `transformers`

## Documentation

- [H.O.R.S.E. V2 topological rules](docs/horse_v2_topological_rules.md)
- [Current game-theoretic framework](docs/current_game_theoretic_framework.md)
- [V3 Wall Street H.O.R.S.E. Persistent Poker](docs/v3_wall_street_horse_persistent/README.md)
- [Local open models](docs/local_open_models.md)
- [Architecture](docs/architecture.md)
- [TOS and safety](docs/tos_safety.md)

## Troubleshooting

- If `persistentpoker-bench` is missing, re-run `pip install -r requirements.txt` inside the active venv.
- If a provider reports missing credentials, confirm `.env` exists and contains the matching uppercase `*_API_KEY`.
- If a model emits verbose text instead of JSON, set `prefer_json_mode: false` in its config; the parser still extracts a normalized decision.
- If LiteLLM/provider routing is unclear, set `LITELLM_DEBUG=true` in `.env` or add `"litellm_debug": true` to one entrant config. This calls `litellm._turn_on_debug()` before requests.
- If video rendering fails, confirm `matplotlib` and `Pillow` came from `requirements.txt`.
- If a run is expensive, reduce `seeds`, `hand_count`, or add `budget_caps`.

## Development Checks

```bash
pytest -q
python -m ruff check src tests
python -m compileall -q src/persistentpoker_bench
```

## License

TBD. MIT or Apache-2.0 are both compatible candidates.
