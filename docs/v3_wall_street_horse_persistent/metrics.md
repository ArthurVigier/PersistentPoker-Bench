# V3 Metrics

V3 keeps all current metrics:

```text
chip_delta
final_stack
survival_rate
win_rate
memory_accuracy
parsing_success_rate
reset_rate
average_pool_size
tokens
estimated_cost
```

It adds market metrics.

## 1. Purchase Metrics

| Metric | Meaning |
|---|---|
| `market_purchase_count` | number of cards bought |
| `market_pass_count` | number of opportunities passed |
| `market_spend_total` | total chips spent buying cards |
| `average_purchase_price` | mean price per bought card |
| `purchase_rate` | purchases divided by market opportunities |
| `affordable_pass_rate` | pass while at least one card was affordable |

## 2. Outcome Metrics

| Metric | Meaning |
|---|---|
| `post_purchase_chip_delta` | chip change after hands with purchases |
| `purchase_hand_win_rate` | win rate on hands where the player bought |
| `non_purchase_hand_win_rate` | win rate on hands where the player did not buy |
| `market_roi` | chip delta per chip spent on Wall Street cards |
| `market_drawdown` | worst stack drop following purchase-heavy sequences |

## 3. Valuation Metrics

Perfect EV is hard to compute. Start with proxies:

| Metric | Proxy |
|---|---|
| `mispricing_capture` | bought cheap cards later used in winning hand |
| `overpay_loss` | expensive purchases followed by fold/loss |
| `denial_success` | bought card blocks opponent-visible draw or low board |
| `variant_fit_score` | card rank/suit usefulness under current variant |
| `pool_fit_score` | usefulness relative to persistent pool composition |

## 4. Risk Metrics

| Metric | Meaning |
|---|---|
| `inventory_risk` | chips spent on bought cards not used at showdown |
| `liquidity_pressure` | fraction of stack spent on market buys |
| `pot_inflation_exposure` | amount added to pots ultimately lost |
| `all_in_after_market_rate` | all-ins after purchase sequences |

## 5. Strategic Metrics

| Metric | Meaning |
|---|---|
| `denial_purchase_rate` | buys likely valuable to an opponent |
| `signal_strength` | public strength revealed by purchases |
| `reset_after_purchase_rate` | resets following market-heavy wins |
| `continue_after_purchase_rate` | continues following market-heavy wins |
| `market_parse_success_rate` | valid market-action parsing |

## 6. Leaderboard Modes

V3 can support multiple leaderboard views:

### Pure Performance

```text
average_chip_delta
final_stack
survival_rate
win_rate
```

### Market Intelligence

```text
market_roi
mispricing_capture
overpay_loss
purchase_hand_win_rate
```

### Agentic Robustness

```text
chip_delta
memory_accuracy
market_parse_success_rate
reset_rate
cost
```

### Risk-Adjusted

```text
chip_delta - lambda_1 * drawdown - lambda_2 * overpay_loss - lambda_3 * cost
```

## 7. Minimum Metrics for First Implementation

Start with:

1. `market_purchase_count`;
2. `market_spend_total`;
3. `average_purchase_price`;
4. `purchase_rate`;
5. `market_roi`;
6. `reset_after_purchase_rate`;
7. `market_parse_success_rate`.

These are enough to diagnose whether models understand the market layer.

