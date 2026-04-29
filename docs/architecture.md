# PersistentPoker-Bench Architecture

## Design Goals

- Reproducible benchmark runs
- Public, inspectable rules
- Strict separation between engine logic and model adapters
- Deterministic fixtures for regression testing
- Low ToS risk through provider-safe orchestration

## Phase-Oriented Architecture

### 1. Core Domain Layer

Planned modules:

- `cards.py`: card models and parsing
- `hand_evaluator.py`: custom evaluator for duplicate-aware categories
- `pool.py`: persistent public pool logic
- `game_state.py`: state container for table, players, streets, and pots
- `betting.py`: no-limit action validation and side pot resolution
- `showdown.py`: winner computation and payout distribution
- `memory_check.py`: believed-pool verification logic

### 2. LLM Integration Layer

Planned modules:

- `prompting.py`: structured prompt rendering
- `schemas.py`: JSON schemas for action and memory outputs
- `adapters/litellm_adapter.py`: provider routing
- `retries.py`: retry, timeout, and parser recovery policies

Parser recovery should be intentionally tolerant:

- Try strict JSON first
- Then try light repair for malformed JSON
- Then try raw-text extraction with regex-based fallbacks
- Always preserve the original raw output for auditability

### 3. Tournament Layer

Planned modules:

- `match_runner.py`: single-table repeated play
- `tournament.py`: multi-match orchestration
- `metrics.py`: benchmark metrics
- `leaderboard.py`: aggregation and export

### 4. Release Layer

Planned assets:

- Python package
- CLI entrypoints
- Hugging Face Space demo
- Public leaderboard export

## Determinism Strategy

- Use seeded scenario fixtures
- Keep all randomness inside an auditable RNG boundary
- Serialize every hand state and model response
- Version rules independently from code release tags

## Safety Strategy

- Benchmark only through documented API usage paths
- Avoid scraping or UI automation against model providers
- Require explicit model adapter configuration by the operator
- Store prompts, parsed outputs, and failures for auditability

## Recommended Public Data Outputs

- Per-hand JSON transcript
- Per-match summary JSON
- Aggregate CSV leaderboard
- Rule version and engine version metadata
