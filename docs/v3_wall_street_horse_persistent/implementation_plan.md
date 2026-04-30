# V3 Implementation Plan

The implementation should be incremental and non-invasive.

## Phase 1: Data Structures

Implemented with a dedicated market module plus small engine extensions:

```text
src/persistentpoker_bench/wall_street.py
src/persistentpoker_bench/hand_runner.py
src/persistentpoker_bench/schemas.py
src/persistentpoker_bench/serialization.py
src/persistentpoker_bench/replay.py
```

Initial dataclasses:

```python
WallStreetSlot(slot: int, card: Card, price: int)
MarketState(slots: tuple[WallStreetSlot, ...])
MarketDecision(type: str, slot: int | None, card: str | None, price: int | None)
MarketPurchase(player_index: int, card: Card, price: int, street: str)
```

## Phase 2: Config

Add optional config keys:

```json
{
  "game_mode": "horse_v3_wall_street",
  "horse_hands_per_game": 2,
  "wall_street_slots": 4,
  "wall_street_price_multipliers": [1, 2, 3, 4],
  "allow_market_all_in": false
}
```

## Phase 3: Prompt Schema

Extend prompt payload with:

```text
market
legal_market_actions
player.market_cards
player.market_spend_total
```

The decision parser normalizes optional V3 fields:

```text
market_action + market_slot + classic betting action
```

while retaining backward compatibility with current `action`.

## Phase 4: Engine Integration

In `run_seeded_hand`:

1. initialize Wall Street row after dealing;
2. before betting action, parse/execute market action;
3. execute betting action;
4. record both actions in transcript;
5. update pot/stack for purchases;
6. replace bought market slots;
7. include market purchases in replay.

## Phase 5: Evaluation

Variant evaluators need access to:

```text
player.market_cards
market card visibility mode
```

Start simple:

| Variant | Bought-card treatment |
|---|---|
| Hold'em | buyer-owned auxiliary candidate, max 1 usable |
| Omaha 8B | public/community candidate |
| Razz | buyer-owned private low candidate |
| Stud | public up-card |
| Stud 8B | public up-card |

## Phase 6: Metrics

Add first metrics:

```text
market_purchase_count
market_spend_total
average_purchase_price
purchase_rate
market_roi
market_parse_success_rate
```

## Phase 7: Replay and Video

Extend:

```text
replay.py
web_ui.py
video_renderer.py
```

with market row, purchases, replacement cards, and market spend charts.

Current implementation already serializes market state in replay artifacts.
Dedicated visual charts remain a follow-up.

## Phase 8: Tests

Minimum test set:

1. market row deals deterministic cards;
2. buy action deducts stack and increases pot;
3. bought slot is replaced;
4. illegal buy falls back to pass;
5. market state serializes without leaking opponent hole cards;
6. reset/continue pool update includes market purchase cards;
7. replay serializes market state;
8. V3 config still runs all H.O.R.S.E variants;
9. CLI demo runs V3 without API keys;
10. model-backed config is JSON-valid.

## Non-Goals for First V3

Avoid initially:

1. auctions;
2. shorting cards;
3. dynamic pricing curves;
4. multi-card market buys per decision;
5. full equilibrium pricing;
6. external market makers.

Those are V3.1/V4 candidates.
