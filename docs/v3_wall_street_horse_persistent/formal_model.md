# V3 Formal Model

This document defines Wall Street H.O.R.S.E Persistent Poker as a finite,
partially observable, stochastic dynamic game with public memory and a priced
card market.

## 1. High-Level Object

Let V3 be the game family:

```text
G_V3 = (N, V, D, S, A, T, O, U, M)
```

where:

| Symbol | Meaning |
|---|---|
| \(N\) | finite player set |
| \(V\) | H.O.R.S.E variant set |
| \(D\) | finite card deck |
| \(S\) | state space |
| \(A\) | joint action space |
| \(T\) | stochastic transition kernel |
| \(O\) | player observation maps |
| \(U\) | payoff functions |
| \(M\) | benchmark measurement function |

The variant set is:

```text
V = {Holdem, Omaha8B, Razz, Stud, Stud8B}
```

The player set is:

```text
N = {1, ..., n}
```

with recommended default:

```text
n = 5
```

## 2. Persistent Public State

At hand \(h\), the persistent pool is a public multiset:

```text
P_h in Multiset(D)
```

The pool is not merely a static feature. It is a strategic state variable whose
future value depends on the winner's governance decision.

At terminal hand state, let \(E_h\) be the exposed candidate multiset:

```text
E_h = exposed board cards
    + public stud up-cards
    + bought public market cards
    + revealed private market cards
```

The winner chooses:

```text
g_h in {continue, reset}
```

and the pool transition is:

```text
P_{h+1} =
  empty multiset      if g_h = reset
  P_h + E_h           if g_h = continue
```

This creates a cross-hand control problem. A player can sacrifice immediate
expected value to alter the future public topology of card availability.

## 3. H.O.R.S.E Variant Rotation

Let \(\rho : \mathbb{N} -> V\) be the variant rotation function.

For configurable `horse_hands_per_game = k`, define:

```text
rho(h) = V_order[floor(h / k) mod |V|]
```

with:

```text
V_order = [Holdem, Omaha8B, Razz, Stud, Stud8B]
```

This matters because the same persistent pool and Wall Street row induce
different values under different evaluation maps.

## 4. Wall Street Market State

At each market opportunity \(t\) inside hand \(h\), the public Wall Street row is:

```text
W_{h,t} = ((c_1,p_1), ..., (c_m,p_m))
```

Recommended default:

```text
m = 4
p_j = j * big_blind
```

Cards are public assets with private, variant-dependent value. A card has no
single scalar value independent of:

1. the current variant \(\rho(h)\);
2. the buyer's private cards;
3. the public board/up-cards;
4. the persistent pool \(P_h\);
5. opponent ranges and budgets;
6. future reset/continue incentives.

## 5. State Decomposition

A full state can be decomposed as:

```text
s_{h,t} = (
  rho(h),
  P_h,
  W_{h,t},
  B_{h,t},
  C^{priv}_{h,t},
  C^{pub}_{h,t},
  stacks_{h,t},
  pot_{h,t},
  history_{h,t},
  actor_{h,t}
)
```

where:

| Term | Meaning |
|---|---|
| \(B_{h,t}\) | board or street structure |
| \(C^{priv}_{h,t}\) | private cards |
| \(C^{pub}_{h,t}\) | public cards and up-cards |
| `stacks` | remaining chip stacks |
| `pot` | current pot |
| `history` | betting, market, and governance history |
| `actor` | acting player |

The benchmark must never expose \(C^{priv}_{-i}\) in player \(i\)'s observation.

## 6. Observation Function

Player \(i\)'s observation is:

```text
o_i = O_i(s)
```

with:

```text
O_i(s) = (
  rho(h),
  P_h,
  W_{h,t},
  B_{h,t},
  C^{priv}_{i,h,t},
  C^{pub}_{h,t},
  public opponent cards,
  stacks_{h,t},
  pot_{h,t},
  public history_{h,t},
  legal actions
)
```

and explicitly:

```text
C^{priv}_{j,h,t} not in O_i(s) for all j != i
```

This preserves the benchmark's private-information boundary while still testing
whether models can reason over public topology.

## 7. Action Space

At a decision point, player \(i\)'s action is a pair:

```text
a_i = (m_i, b_i)
```

where \(m_i\) is a market action and \(b_i\) is a betting action.

The minimal market action space is:

```text
M_i(s) = {pass_market} union {buy(j) : j is affordable and legal}
```

The betting action space is inherited from the current poker engine:

```text
B_i(s) subset {fold, check, call, bet, raise, all_in}
```

Thus:

```text
A_i(s) = M_i(s) x B_i(s)
```

In implementation, these may be requested as one structured JSON object and
normalized into an executable pair.

## 8. Transition Kernel

The transition kernel factorizes into:

```text
T(s' | s, a_i) =
  T_market(s_m | s, m_i)
  * T_betting(s_b | s_m, b_i)
  * T_deal(s' | s_b)
```

For `buy(j)`, the market transition is:

```text
stack_i' = stack_i - p_j
pot' = pot + p_j
market_cards_i' = market_cards_i + c_j
W'[j] = fresh_card(D_remaining)
history' = history + buy_event(i, c_j, p_j)
```

For `pass_market`, the market state is unchanged except for history if pass
events are logged.

## 9. Utility

The base hand payoff is chip delta:

```text
u_i^{chip}(h) = stack_{i,h,end} - stack_{i,h,start}
```

The match payoff is:

```text
U_i = sum_h u_i^{chip}(h)
```

The benchmark can also evaluate auxiliary objectives:

```text
u_i^{memory}
u_i^{market}
u_i^{governance}
u_i^{format_adaptation}
```

These are not paid to the model as chips, but they are measured to diagnose
competence.

## 10. Market Value Function

For a visible card \(c\) at price \(p\), define player \(i\)'s subjective
incremental market value:

```text
Delta_i(c, p | o_i) =
  E_i[U_i | buy(c,p), o_i] - E_i[U_i | pass_market, o_i]
```

A buy is locally rational when:

```text
Delta_i(c, p | o_i) > 0
```

But V3 makes this difficult because \(\Delta_i\) includes:

1. immediate hand equity;
2. pot inflation;
3. denial value against opponents;
4. signaling cost;
5. persistent-pool effect;
6. future variant-dependent value.

## 11. Strategic Couplings

V3 intentionally couples several games:

| Coupling | Description |
|---|---|
| Poker equity | ordinary hand strength and pot odds |
| Market pricing | whether public card price is mispriced |
| Denial | buying to prevent opponent access |
| Signaling | purchase reveals information or intent |
| Memory | pool belief must match public history |
| Governance | winner controls reset/continue |
| Variant adaptation | value changes across H.O.R.S.E modes |

The hard part is not any one component. The hard part is that each local action
changes the payoff landscape for the others.

## 12. Equilibrium Intuition

A stable policy should approximate a mixed strategy over:

```text
market aggression
betting aggression
pool governance
variant-specific valuation
opponent exploitation
```

The benchmark is interesting when dominated-looking actions become rational
under a wider state horizon, for example:

1. buying a bad immediate card to deny a strong Razz low card;
2. buying an expensive card to increase fold equity;
3. continuing a pool that slightly hurts now but benefits future Omaha 8B lows;
4. resetting a pool that helped win the hand but creates too much future chaos;
5. passing a cheap card because the signal leak is too expensive.

## 13. Benchmark Measurement Function

Let \(M\) map full transcripts to metrics:

```text
M : histories -> R^d
```

Recommended dimensions:

```text
M(history) = (
  chip_ev,
  win_rate,
  market_roi,
  market_purchase_accuracy,
  denial_efficiency,
  pool_memory_accuracy,
  governance_quality,
  variant_adaptation_score,
  invalid_action_rate,
  parse_success_rate
)
```

This makes V3 useful not only as a poker benchmark, but as an architecture probe
for planning, memory, valuation, hidden information, and strategic control.

