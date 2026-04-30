# V3: Wall Street H.O.R.S.E Persistent Poker

This subdirectory sketches a V3 benchmark backbone that combines:

```text
H.O.R.S.E rule rotation
+ persistent public card pool
+ Wall Street card market
= strategic memory-market poker
```

The goal is not to replace V2 immediately. V3 is a research design layer for a
harder benchmark where agents must reason about changing poker rules, persistent
public state, priced public card acquisition, risk, signaling, and market-like
mispricing.

## Core Idea

In V2, agents answer:

```text
What is the best poker action under this variant and persistent pool?
```

In V3, agents answer:

```text
What is the best combined poker + market action under this variant,
with this persistent pool, these visible priced assets, and these opponents?
```

The Wall Street row turns public cards into priced assets. Buying a card can
improve a hand, deny an opponent, grow the pot, signal strength, or create
future persistent-pool consequences.

## Files

- [`rules.md`](./rules.md): concrete game rules and phase order.
- [`state_action_schema.md`](./state_action_schema.md): proposed state and JSON decision schema.
- [`metrics.md`](./metrics.md): benchmark metrics added by the market layer.
- [`game_theory.md`](./game_theory.md): strategic phenomena and equilibrium pressure.
- [`formal_model.md`](./formal_model.md): mathematical model of state, observations, actions, transitions, and measurement.
- [`visualization.md`](./visualization.md): how to visualize a V3 hand/run.
- [`implementation_plan.md`](./implementation_plan.md): low-risk integration plan.
- [`example_config.json`](./example_config.json): example config shape.

## Design Principle

V3 should remain comparable to V2:

1. same tournament runner style;
2. same replay/artifact philosophy;
3. same `believed_pool` memory audit;
4. same reset/continue governance;
5. one extra market phase, not a full economic simulator.

The market layer should be small enough to implement and visualize, but rich
enough to reveal valuation, risk, and manipulation failures.

## Runnable Implementation

The minimal V3 engine is implemented as:

```text
game_mode = horse_v3_wall_street
```

Runnable local smoke command:

```bash
persistentpoker-bench demo \
  --track frontier \
  --hands 2 \
  --seeds 20260430 \
  --game-mode horse_v3_wall_street \
  --horse-hands-per-game 2 \
  --outdir ./artifacts/horse-v3-wall-street-demo
```

Runnable model-backed command:

```bash
persistentpoker-bench run \
  --config ./configs/horse_v3_wall_street_claude_diverse_2026-04-30.json \
  --outdir ./artifacts/horse-v3-wall-street-frontier-2026-04-30
```

The first implementation supports fixed-price card buys with:

```json
{
  "wall_street_slots": 4,
  "wall_street_price_multipliers": [1, 2, 3, 4],
  "allow_market_all_in": false
}
```
