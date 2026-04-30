# V3 Game-Theoretic Interpretation

V3 changes the benchmark from:

```text
imperfect-information poker with persistent public memory
```

to:

```text
imperfect-information poker with persistent public memory and priced public assets
```

## 1. Public Card, Private Value

A Wall Street card is public:

```text
everyone sees Ah at price 80
```

but its value is private:

```text
Ah may complete my low draw, improve your high hand, block another player,
or be irrelevant to someone else.
```

This creates a valuation game:

\[
Value_i(c,p,v,P,h) = PrivateUse_i(c,v,h) - Price(c) + StrategicExternality_i(c,P)
\]

where:

| Term | Meaning |
|---|---|
| \(c\) | market card |
| \(p\) | price |
| \(v\) | current H.O.R.S.E variant |
| \(P\) | persistent pool |
| \(h\) | hand/private history |

## 2. Buy/Pass as Signal

Buying a card reveals information:

```text
If I buy a low card in Razz, opponents infer I care about low strength.
If I buy a suited ace in Hold'em, opponents infer flush/high potential.
```

Thus a market action has:

1. direct hand value;
2. pot-inflation effect;
3. signal effect;
4. denial effect;
5. persistent-pool effect.

## 3. Denial Purchases

Sometimes a card is more valuable to an opponent than to the buyer.

Denial buy condition:

\[
Value_i(c) < Price(c)
\]

but:

\[
Value_j(c) - Price(c) \gg 0
\]

Then buying may be rational if:

\[
PreventedGain_j(c) > Overpay_i(c)
\]

This is market defense, not hand improvement.

## 4. Pot Inflation

Because purchase price enters the pot, buying changes the reward structure.

If player \(i\) buys card \(c\) for \(p\):

\[
Pot' = Pot + p
\]

This can be rational even for a marginal card when the buyer has a strong
showdown edge:

\[
\Pr_i(win) \cdot Pot' - p > \Pr_i(win) \cdot Pot
\]

But if the buyer later folds or loses:

\[
p
\]

becomes a transfer to the eventual winner.

## 5. Persistent Pool Coupling

A bought public card may enter the persistent pool after the hand.

Thus the market also changes the future:

\[
P_{h+1}=P_h+E_h+BoughtPublic_h
\]

unless reset.

This adds a governance layer:

```text
buy useful card -> win -> reset to erase cognitive pollution
buy useful card -> win -> continue to preserve advantage
buy toxic card -> lose -> opponent inherits polluted pool
```

## 6. Variant Arbitrage

Cards have variant-dependent values:

| Card type | Hold'em | Omaha 8B | Razz | Stud | Stud 8B |
|---|---|---|---|---|---|
| A | high premium | high/low flexible | low premium | high premium | high/low flexible |
| K/Q/J/T | high value | high value | lowball liability | high value | high-only |
| 2/3/4/5 | low pair/draw value | low qualifier | premium | weak high | low qualifier |
| suited connector | draw value | constrained draw value | mostly irrelevant | visible draw signal | mixed |

The agent must price cards under the current regime, not by generic poker
intuition.

## 7. Bounded Rationality

V3 is especially hard for LLMs because it stacks:

1. rule switching;
2. persistent memory;
3. private information;
4. priced public assets;
5. pot odds;
6. opponent modeling;
7. JSON/tool compliance.

The likely failure modes:

| Failure | Example |
|---|---|
| variant drift | buying K in Razz because it is "high value" |
| price blindness | buying every useful card regardless of cost |
| denial blindness | leaving cheap opponent-critical cards available |
| pot blindness | buying cards that inflate a pot the model later folds |
| signal blindness | revealing hand direction through purchases |
| reset blindness | continuing polluted pools after market-heavy wins |

## 8. Research Hypothesis

V3 should separate model families more sharply than V2.

Expected profile differences:

| Model trait | V3 effect |
|---|---|
| strong rules | better variant-specific pricing |
| strong arithmetic | better price/pot decisions |
| strong memory | better pool-aware valuation |
| strong metacognition | better reset after market pollution |
| strict formatting | better market-action compliance |
| low verbosity | lower cost and fewer schema failures |

The benchmark becomes less about knowing poker and more about acting inside a
small reflexive economy.

