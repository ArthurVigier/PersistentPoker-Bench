# V3 Visualization

V3 needs visualization that makes three things visible at once:

1. poker table state;
2. persistent pool memory;
3. Wall Street market row.

## 1. Table Layout

Recommended scene:

```text
                         Persistent Pool
        [Ah] [Kd] [7c] [7d] [2s] [Qh] ...

                  Wall Street Market
        +---------+---------+---------+---------+
        |  2h     |  Ks     |  7d     |  Ah     |
        | $20     | $40     | $60     | $80     |
        +---------+---------+---------+---------+

      Player 1                                Player 2
    stack / cards                           stack / cards

                       Pot: 340
                    Board / Street

      Player 5                                Player 3

                       Player 4
```

## 2. Market Interaction Animation

When a player buys:

```text
1. highlight selected market card;
2. animate chips from player to pot;
3. move card to player's market inventory/up-cards;
4. replace market slot from deck;
5. append event to timeline.
```

## 3. Replay Panels

Each replay frame should show:

| Panel | Contents |
|---|---|
| Table | players, stacks, board/up-cards, pot |
| Market | Wall Street row with prices |
| Pool | persistent pool, pool size, reset status |
| Decision | raw action, market action, betting action |
| Metrics | memory accuracy, parse mode, spend, cost |

## 4. Useful Graphs

Across a run:

1. stack trajectories;
2. market spend by player;
3. purchase count by variant;
4. reset/continue after purchase-heavy wins;
5. pool size over time;
6. market ROI by model;
7. parse failures by action type;
8. card prices bought over time.

## 5. Visual Diagnosis Examples

### Overpay Collapse

```text
Player buys expensive card -> pot inflates -> player folds river -> stack drops
```

Visualization should show the purchased card and subsequent loss clearly.

### Denial Buy

```text
Player buys cheap 3 in Razz while opponent shows A-2-4
```

Visualization should mark the card as potentially opponent-critical.

### Reset Trader

```text
Player buys several cards -> wins hand -> resets pool
```

Visualization should show the pool being cleared after a market-heavy win.

