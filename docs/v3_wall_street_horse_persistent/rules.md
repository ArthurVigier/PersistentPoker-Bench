# V3 Rules: Wall Street H.O.R.S.E Persistent Poker

## 1. Components

Each hand has four interacting components:

| Component | Meaning |
|---|---|
| Variant | one H.O.R.S.E mode: Hold'em, Omaha 8B, Razz, Stud, Stud 8B |
| Persistent pool | public multiset carried across hands unless reset |
| Wall Street row | visible priced card row available for purchase |
| Betting game | ordinary betting/fold/showdown pressure |

## 2. Wall Street Row

At the start of each hand, deal a public row:

```text
W_h = [(c_1,p_1), (c_2,p_2), (c_3,p_3), (c_4,p_4)]
```

Default prices:

```text
p = [1, 2, 3, 4] big-blind units
```

For example, if big blind is 20:

```text
[2h price=20] [Ks price=40] [7d price=60] [Ah price=80]
```

Prices are paid into the pot when bought.

## 3. Market Phase Timing

Recommended V3 timing:

```text
street begins
-> market decision opportunity for eligible actors
-> betting decision
-> next actor / street
```

To keep implementation tractable, each acting player may make at most one
market action per betting opportunity.

## 4. Market Actions

An agent may choose one market action:

| Action | Meaning |
|---|---|
| `pass_market` | buy nothing |
| `buy_card` | pay listed price and acquire one Wall Street card |

Optional later extensions:

| Action | Meaning |
|---|---|
| `reserve_card` | pay small fee to deny purchase until next actor |
| `short_card` | bet against a card becoming useful |
| `auction_card` | initiate competitive bidding |

V3 should start with only `pass_market` and `buy_card`.

## 5. Buying a Card

If player \(i\) buys \((c_k,p_k)\):

1. \(p_k\) chips are committed by player \(i\);
2. the pot increases by \(p_k\);
3. \(c_k\) is added to player \(i\)'s hand context according to the current variant;
4. the bought slot is replaced by a fresh card from the deck;
5. the purchase is recorded in the public action history.

If the player cannot afford the full price, either:

1. the buy is illegal; or
2. the player may buy all-in if `allow_market_all_in=true`.

Recommended default: market buys cannot exceed stack and do not auto-all-in
unless explicitly configured.

## 6. Variant-Specific Meaning

The same Wall Street card has different value by variant.

### Hold'em

A bought card enters the buyer's private auxiliary hand inventory. At showdown,
the buyer may evaluate using:

```text
hole cards + board + persistent pool + bought cards
```

Recommended constraint:

```text
max 1 bought card contributes to final 5-card hand
```

This prevents market buys from completely overwhelming poker.

### Omaha 8B

Omaha must preserve its strict structure.

Recommended rule:

```text
bought cards count as public/community candidates,
not private hole cards.
```

The player still uses exactly:

```text
2 private hole cards + 3 public candidates
```

where public candidates include:

```text
board + persistent pool + bought cards
```

### Razz

Bought cards become private lowball candidates for the buyer.

This creates strong valuation pressure:

```text
A, 2, 3, 4, 5 are premium assets
K, Q, J, T are toxic assets
```

### Stud

Bought cards become buyer-owned visible cards unless configured otherwise.

Recommended default:

```text
bought cards are public up-cards
```

This creates signaling: buying a strong visible card improves hand potential
but reveals information.

### Stud 8B

Bought cards can support high or qualifying low.

Low cards become flexible assets:

```text
A, 2, 3, 4, 5, 6, 7, 8
```

but paired low cards may be less valuable for low qualification.

## 7. Persistent Pool Update

At hand end, the pool candidate update becomes:

```text
E_h = exposed board cards + stud up-cards + bought public cards
```

Then winner governance applies:

```text
P_{h+1} = 0              if winner chooses reset
P_{h+1} = P_h + E_h     if winner chooses continue
```

Bought private cards should enter the persistent pool only if they were
revealed by showdown or configured as public.

## 8. Recommended Minimal V3

Start with this rule set:

1. 5-player table;
2. H.O.R.S.E rotation configurable by `horse_hands_per_game`;
3. 4-card Wall Street row;
4. fixed prices `[1,2,3,4] * big_blind`;
5. one optional market buy before each betting action;
6. market buy price goes into pot;
7. bought cards are recorded separately as `market_cards`;
8. reset/continue unchanged;
9. all market state is included in replay/video artifacts.

This is enough to test valuation without making the system unbounded.

