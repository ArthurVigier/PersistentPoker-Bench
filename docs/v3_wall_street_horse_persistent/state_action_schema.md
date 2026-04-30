# V3 State and Action Schema

## 1. State Additions

V3 extends the current decision snapshot with a market state:

```json
{
  "market": {
    "street_market_open": true,
    "wall_street": [
      { "slot": 0, "card": "2h", "price": 20 },
      { "slot": 1, "card": "Ks", "price": 40 },
      { "slot": 2, "card": "7d", "price": 60 },
      { "slot": 3, "card": "Ah", "price": 80 }
    ],
    "purchases_this_hand": [
      {
        "player_index": 2,
        "card": "5c",
        "price": 20,
        "street": "fourth_street"
      }
    ]
  }
}
```

Each player snapshot gains:

```json
{
  "market_cards": ["5c"],
  "market_spend_total": 20
}
```

For privacy:

| Field | Visible to whom |
|---|---|
| own private hole/down cards | acting player only |
| opponent private hole/down cards | never during play |
| up-cards | all players |
| Wall Street row | all players |
| market purchase history | all players |
| bought public cards | all players |
| bought private cards | owner only until showdown |

## 2. Decision Schema Option A: Combined Object

The cleanest V3 decision schema:

```json
{
  "market_action": {
    "type": "buy_card",
    "slot": 0,
    "card": "5c",
    "price": 20
  },
  "betting_action": {
    "type": "check",
    "amount": null
  },
  "believed_pool": ["Ah", "Kd", "7c"],
  "winner_pool_decision": "reset",
  "reasoning": "In Razz, 5c is a strong low card at the cheapest slot."
}
```

`market_action.type` is one of:

```text
pass_market, buy_card
```

`betting_action.type` is one of:

```text
fold, check, call, bet, raise, all_in
```

## 3. Decision Schema Option B: Flattened Backward-Compatible Object

If backward compatibility is preferred:

```json
{
  "action": "check",
  "amount": null,
  "market_action": "buy_card",
  "market_slot": 0,
  "market_card": "5c",
  "market_price": 20,
  "believed_pool": ["Ah", "Kd", "7c"],
  "winner_pool_decision": "reset",
  "reasoning": "Buying 5c improves my Razz low at a low price."
}
```

This is easier to integrate with the current parser but less elegant.

## 4. Recommended V3 Schema

Use Option A internally, but allow fallback parsing from Option B.

Reason:

1. Option A separates market and betting logic cleanly.
2. Option B helps with model compliance and old adapters.
3. The normalized transcript can always store both as structured fields.

## 5. Legal Market Actions Snapshot

The prompt should include:

```json
{
  "legal_market_actions": {
    "can_pass_market": true,
    "can_buy_card": true,
    "affordable_slots": [0, 1, 2],
    "max_market_price": 60
  }
}
```

This mirrors the current `legal_actions` object for betting.

## 6. Transcript Event Additions

Each action event should record:

```json
{
  "market_decision": {
    "type": "buy_card",
    "slot": 0,
    "card": "5c",
    "price": 20
  },
  "executed_market_action": {
    "type": "buy_card",
    "slot": 0,
    "card": "5c",
    "price": 20
  },
  "market_result": {
    "pot_delta": 20,
    "replacement_card": "Qh"
  }
}
```

If invalid, normalize to:

```json
{
  "executed_market_action": {
    "type": "pass_market"
  }
}
```

