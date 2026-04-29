# Provider Strategy and Current Model Targets (2026-04-28)

## Objective

This document captures a time-stamped integration recommendation for the next
PersistentPoker-Bench milestone:

- select current model targets
- manage inference cost responsibly
- choose the right client libraries and API surfaces
- wire the benchmark engine to real model providers reproducibly

## Date Anchor

This recommendation is based on provider documentation checked on April 28, 2026.
Model lineups, aliases, pricing, and feature support can change later, so this
document should be treated as a dated benchmark policy input rather than a
timeless truth.

## Current Provider Reality

### DeepSeek

Current official API focus:

- `deepseek-v4-pro`
- `deepseek-v4-flash`

Notes:

- DeepSeek V4 Preview was announced on April 24, 2026.
- `deepseek-chat` and `deepseek-reasoner` are compatibility aliases routing to
  V4 Flash modes for now, but are scheduled for retirement.
- Both V4 models support 1M context, thinking and non-thinking modes, JSON
  output, tool calls, and OpenAI-compatible calls.

### xAI

Current official API focus:

- `grok-4.20-reasoning`
- `grok-4.20-non-reasoning`
- `grok-4-1-fast-reasoning`
- `grok-4-1-fast-non-reasoning`

Notes:

- xAI documentation presents Grok 4.20 as the newest flagship family.
- xAI supports OpenAI-style access and also its own `xai_sdk`.
- Prompt caching and batch APIs are documented first-class features.

### Qwen / Alibaba Cloud Model Studio

Current official hosted API focus:

- `qwen3-max`
- `qwen3-max-2026-01-23`
- `qwen3.5-plus`
- `qwen3.5-flash`

Important implication:

- `Qwen3-72B` is no longer the best current hosted benchmark target if the goal
  is "state of the art API benchmarking."
- For hosted benchmarking, `qwen3-max` or `qwen3.5-plus` is the current stronger
  target, while `qwen3.5-flash` is the cost-efficient comparison tier.

### Gemini

Current official API focus:

- `gemini-3.1-pro-preview`
- `gemini-3-flash-preview`
- `gemini-3.1-flash-lite-preview`
- `gemini-2.5-pro`
- `gemini-2.5-flash`

Notes:

- Gemini 3 Pro Preview has been shut down and Google explicitly tells developers
  to migrate to `gemini-3.1-pro-preview`.
- Gemini 3.1 Pro is the current highest-end benchmark target in the Gemini
  family for complex reasoning and coding.
- Google exposes both a native SDK path and an OpenAI-compatibility path.

### OpenAI

Current official API focus:

- `gpt-5.5`
- `gpt-5.4`
- `gpt-5.4-mini`
- `gpt-5.4-nano`
- `gpt-5.5-pro`

Important implication:

- The earlier `GPT-5.2 / GPT-5.4` recommendation is no longer fully current.
- As of April 28, 2026, OpenAI’s model docs present `gpt-5.5` as the flagship.

## Recommended Benchmark Target Sets

### Set A: Current Frontier API Track

Use this when the benchmark wants to represent the live frontier as of
2026-04-28:

- DeepSeek: `deepseek-v4-pro`
- xAI: `grok-4.20-reasoning`
- Qwen: `qwen3-max`
- Gemini: `gemini-3.1-pro-preview`
- OpenAI: `gpt-5.5`

### Set B: Safe Budget Companion Track

Use this when you want a lower-cost mirror for large tournament volume:

- DeepSeek: `deepseek-v4-flash`
- xAI: `grok-4-1-fast-reasoning`
- Qwen: `qwen3.5-flash`
- Gemini: `gemini-3.1-flash-lite-preview`
- OpenAI: `gpt-5.4-mini`

### Set C: Reproducibility Snapshot Track

When available, prefer snapshot IDs over moving aliases for published benchmark
results:

- OpenAI: prefer dated snapshots when published
- Qwen: use dated snapshots such as `qwen3-max-2026-01-23`
- Gemini: preview IDs are moving targets, so archive the exact string and date
- DeepSeek: use `deepseek-v4-pro` and record the evaluation date because the
  stable alias is current official guidance
- xAI: record the exact model ID and evaluation date

## Cost Management Policy

### 1. Separate interactive benchmarking from bulk benchmarking

Use two inference modes:

- Interactive mode:
  for local debugging, single-hand inspection, parser validation, and prompt
  iteration.
- Bulk mode:
  for large tournament evaluation using batch APIs when supported.

### 2. Prefer cheap models for dev loops

For developer iteration, default to:

- DeepSeek `deepseek-v4-flash`
- xAI `grok-4-1-fast-reasoning`
- Qwen `qwen3.5-flash`
- Gemini `gemini-3.1-flash-lite-preview`
- OpenAI `gpt-5.4-mini`

Reserve frontier models for:

- milestone evaluations
- leaderboard submissions
- regression baselines

### 3. Exploit provider-native cost reducers

- OpenAI:
  prompt caching is automatic on recent models and Batch API offers a 50%
  discount.
- Gemini:
  Batch API is 50% of standard cost, and context caching is available with both
  implicit and explicit modes.
- DeepSeek:
  context caching is automatic, with explicit cache hit accounting in usage.
- xAI:
  prompt caching is automatic and batch processing is documented for large jobs.
- Qwen:
  batch invocation is 50% off on supported models and context-cache discounts
  are documented.

### 4. Keep prompts cache-friendly

Shared static prefix first:

- rules summary
- output schema
- benchmark instructions

Variable content last:

- current hand state
- believed pool target
- legal actions

This increases the chance of cache hits across repeated hands.

### 5. Use hard caps to prevent runaway spend

Each benchmark call should enforce:

- `temperature=0`
- explicit `max_tokens`
- per-request timeout
- retry cap
- optional daily and per-model budget ceiling

### 6. Keep reasoning bounded

To make cross-provider comparisons less distorted by hidden extra compute:

- use each provider’s standard reasoning-capable flagship by default
- avoid "pro" or multi-agent premium variants for the baseline track
- if premium variants are evaluated, publish them as a separate leaderboard tier

## Recommended Library Stack

### Core

- `litellm`
  unified routing layer for multi-provider calls
- `openai`
  useful as the common OpenAI-compatible client when a provider supports that
  surface directly
- `pydantic`
  for optional typed schema validation in addition to the tolerant parser

### Provider-specific optional libraries

- `google-genai`
  use when you need Gemini-native features beyond the OpenAI-compatible bridge,
  especially file upload/download, explicit caching, and the full native batch
  workflows
- `xai_sdk`
  optional if xAI-specific advanced features become easier through the native SDK

### Libraries to avoid in the core benchmark path

- avoid making LangChain the primary execution path
- avoid agent frameworks in the benchmark hot path
- avoid provider-specific orchestration logic inside the game engine

The benchmark should stay close to raw API behavior.

## Recommended Integration Surface

### First choice

Use LiteLLM plus OpenAI-compatible chat style requests as the default benchmark
transport for all providers that support it.

This is the best default for:

- DeepSeek
- xAI
- Qwen / Model Studio
- Gemini through OpenAI compatibility
- OpenAI

### Second choice

Use provider-native SDKs only when a benchmark feature requires them:

- Gemini file upload/download for batch assets
- Gemini explicit cache lifecycle management
- special provider telemetry not exposed through the compatibility layer

## Exact Wiring for the Next Milestone

### 1. Standardize `game_snapshot`

Create a serializer from `HandState` with a stable key order:

- `hand_id`
- `street`
- `button_index`
- `actor_index`
- `pot_total`
- `current_bet`
- `last_full_raise_size`
- `community_cards`
- `persistent_pool`
- `players`

For each player:

- `seat`
- `name`
- `stack`
- `committed_street`
- `committed_total`
- `folded`
- `all_in`
- `is_self`
- `hole_cards` only for the acting player

### 2. Standardize `legal_actions`

Serialize directly from `get_legal_actions(...)`:

- `can_fold`
- `can_check`
- `can_call`
- `can_bet`
- `can_raise`
- `can_all_in`
- `call_amount`
- `min_bet_to`
- `min_raise_to`
- `max_to`

### 3. Build prompt

Use `build_decision_prompt(...)` with:

- compact standardized snapshot
- legal actions
- seat metadata

### 4. Call model

Use `request_decision_via_litellm(...)` with:

- provider-qualified model IDs where needed
- per-model config
- bounded retries

### 5. Parse and inject action

Pipeline:

1. parse raw output
2. validate against legal actions
3. if invalid:
   mark parse failure, retry if allowed
4. if still invalid:
   apply deterministic fallback policy

Recommended fallback policy:

- if check is legal: `check`
- else if call is legal: `call`
- else: `fold`

### 6. Log benchmark evidence

Per decision, log:

- provider
- model_id
- model_alias
- evaluation_date
- prompt version
- raw_text
- parse_mode
- attempts
- believed_pool
- normalized_decision
- legal_actions_snapshot
- usage if available
- cached token fields if available
- latency

## Implementation Recommendation

The next code milestone should create:

- `src/persistentpoker_bench/serialization.py`
- `src/persistentpoker_bench/hand_runner.py`
- `src/persistentpoker_bench/model_registry.py`
- `tests/test_serialization.py`
- `tests/test_hand_runner.py`

## Final Recommendation

For the first public benchmark release, keep two official tracks:

- Frontier track:
  `deepseek-v4-pro`, `grok-4.20-reasoning`, `qwen3-max`,
  `gemini-3.1-pro-preview`, `gpt-5.5`
- Efficiency track:
  `deepseek-v4-flash`, `grok-4-1-fast-reasoning`, `qwen3.5-flash`,
  `gemini-3.1-flash-lite-preview`, `gpt-5.4-mini`

This gives you both prestige and scale without exploding cost.

## Accepted Project Decisions

The project decisions accepted after this strategy review are:

- replace the legacy shortlist with the current shortlist above
- publish two official leaderboards: `frontier` and `efficiency`
- require a deterministic seed mode for reproducible benchmark runs
