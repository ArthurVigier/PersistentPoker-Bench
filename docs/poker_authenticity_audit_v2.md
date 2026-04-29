# PersistentPoker-Bench: Poker Authenticity Audit and V2 Proposal

Date: 2026-04-29

## Goal

This document audits the gap between real no-limit Texas Hold'em match logic and the current
PersistentPoker-Bench implementation. It then proposes a V2 that keeps the benchmark's memory
signal while making the poker environment substantially more authentic.

## Executive Summary

The current implementation is a strong "LLM decision-under-imperfect-information + persistent
memory" benchmark, but it is not yet a faithful model of an actual poker session.

It is poker-authentic at the hand engine level:
- private hole cards
- shared board
- no-limit action space
- blinds
- side pots
- multi-way showdown

It is not yet poker-authentic at the session level:
- stacks reset every hand
- players are never eliminated
- chip accumulation does not persist across hands
- match success is measured mostly by hand wins, not by chip profit or survival
- the custom evaluator changes strategic incentives far beyond standard hold'em

Conclusion:
- Current v1 is suitable as a benchmark for strategic reasoning, action formatting, and pool memory.
- Current v1 is not yet a strong benchmark for "real poker skill" in the usual competitive sense.

## What Already Matches Real Poker

### 1. Imperfect information

Only the acting player receives their own hole cards in the serialized game snapshot.
Other players' hole cards are not exposed.

Impact:
- good approximation of real poker information structure
- supports bluffing, uncertainty, and belief-based decisions

### 2. No-limit action structure

The engine supports:
- fold
- check
- call
- bet
- raise
- all-in

It also enforces:
- amount-to-call logic
- min raise logic
- stack-bounded actions
- all-in reopening rules

Impact:
- good approximation of a real betting round

### 3. Multi-player pots and side pots

The showdown layer builds side pots from total commitments and allocates each pot only among
eligible players.

Impact:
- important real-poker feature already present

### 4. Position and blinds

The hand model includes:
- button
- small blind
- big blind
- preflop order
- postflop acting order

Impact:
- preserves one of the core strategic dimensions of hold'em

## Main Deviations From Real Poker

### 1. Stacks reset every hand

Current behavior:
- each hand calls `create_hand_state(...)`
- every player is recreated with the same starting stack

Why this matters:
- removes bankroll pressure
- removes bust-out risk
- removes short-stack and deep-stack adaptation
- removes inter-hand strategic carryover

Real-poker consequence:
- this is the single biggest authenticity gap

### 2. No persistent chip economy across a match

Current behavior:
- only the public persistent pool carries over between hands
- chip gains/losses do not carry over

Why this matters:
- winning a large pot has no future leverage
- losing chips has no future penalty
- players cannot exploit opponents' changing effective stacks

Real-poker consequence:
- match-level strategy is flattened into repeated hand-level tactics

### 3. No eliminations, re-entry pressure, or tournament survival

Current behavior:
- nobody busts out across a multi-hand match

Why this matters:
- no survival incentive
- no laddering behavior
- no strategic asymmetry from chip leader vs short stack

Real-poker consequence:
- benchmark cannot currently measure tournament intelligence

### 4. Success is measured too much by hand wins

Current behavior:
- primary metrics include win count / win rate
- cost, parsing, and memory are aggregated per action
- no primary metric for persistent chip EV or final stack ranking

Why this matters:
- poker is not fundamentally about "most hands won"
- a player can win fewer hands and still play much better

Real-poker consequence:
- benchmark may reward tactical hand outcomes over economically correct play

### 5. The hand evaluator is intentionally non-standard

Current behavior:
- showdown strength is computed from:
  - hole cards
  - community cards
  - full persistent pool
- custom categories include:
  - Double Royal Flush
  - Five of a Kind
  - Double Straight Flush
  - Four of a Kind + Flush
  - Full House + Flush

Why this matters:
- this radically changes hand values
- standard hold'em priors do not transfer cleanly
- pool memory can dominate normal board-reading skill

Real-poker consequence:
- this is acceptable for benchmark novelty, but it means the benchmark is no longer testing
  standard poker expertise

### 6. Match state does not encode long-term opponent modeling

Current behavior:
- the benchmark exposes current hand state and persistent public pool
- there is no standardized history summary of prior betting tendencies, showdown reveals, or
  per-opponent population stats

Why this matters:
- real players adapt to opponent frequencies over time
- in a long session, this is a major skill component

Real-poker consequence:
- current benchmark under-measures exploitation and adaptation

### 7. Dice-based tie resolution is benchmark-practical but non-standard

Current behavior:
- administrative ambiguities are broken by deterministic d6 rolls

Why this matters:
- this is acceptable for benchmark reproducibility
- but it is not how real poker rules would normally adjudicate every edge case

Real-poker consequence:
- low impact on core skill measurement
- acceptable if clearly documented as benchmark policy

## What The Current Benchmark Is Actually Best At Measuring

The current system most strongly measures:
- action selection under uncertainty
- adherence to legal no-limit action constraints
- memory of a duplicated public card pool
- ability to remain structured under long prompts and custom rules
- reasoning under a non-standard combinatorial showdown system

It is weaker at measuring:
- real bankroll management
- tournament survival skill
- exploitative adaptation over long sessions
- chip-EV maximization across many hands

## V2: More Poker-Authentic Architecture

## V2 Principle

Keep the persistent pool innovation, but move from "independent hands with memory" to
"continuous matches with memory and chip persistence."

### V2.1 Persistent stacks across hands

Change:
- introduce a `MatchState` or `TableSessionState`
- player stacks persist after every hand
- only live players with chips continue

Effect:
- restores economic continuity
- enables real short-stack/deep-stack dynamics

### V2.2 Elimination and match termination

Change:
- players can bust out
- match ends when one player has all chips, or after a fixed hand cap

Effect:
- introduces survival pressure
- enables ranking by finish position

### V2.3 Primary scoring by chips, not hand count

Replace or demote:
- hand win rate

Promote:
- final stack
- chips won/lost
- normalized bb/100 proxy
- finish position

Effect:
- benchmark aligns more closely with real poker incentives

### V2.4 Session-level opponent history

Add to snapshot:
- prior actions by seat
- showdown reveal summaries when applicable
- simple opponent statistics:
  - VPIP proxy
  - PFR proxy
  - aggression ratio proxy

Effect:
- measures opponent adaptation, not just isolated tactical play

### V2.5 Distinguish benchmark variants

Create two explicit tracks:

#### Track A: Benchmark-Original
- persistent pool affects showdown
- custom hand categories remain

Use case:
- memory-heavy, novel benchmark track

#### Track B: Poker-Authentic
- persistent pool remains visible and recallable
- but showdown uses standard hold'em cards only, or the pool affects bonus scoring rather than hand ranking

Use case:
- closer to true poker skill

Effect:
- avoids conflating "real poker" with "custom memory game"

### V2.6 Better match formats

Recommended formats:
- 3-max and 4-max cash-session style with persistent stacks
- optional SNG-style tournament format

Avoid as primary benchmark:
- single independent hand score aggregation

### V2.7 More realistic evaluation outputs

For each model, report:
- final stack distribution
- average chip delta per hand
- bust-out count
- finish position frequency
- memory accuracy
- parsing success
- cost per 100 hands

## Recommended Roadmap

### Phase V2-A: Core authenticity upgrade
- add persistent stacks across hands
- add bust-out handling
- add match termination rules
- add final-stack metrics

### Phase V2-B: Benchmark split
- split into `benchmark_original` and `poker_authentic`
- preserve the current evaluator only in the original track

### Phase V2-C: Opponent adaptation
- add history summaries and seat-level tendency stats to the prompt snapshot

## Final Recommendation

If the goal is:

### "best LLM memory benchmark with poker flavor"
Keep v1 mostly as-is.

### "best public benchmark for actual poker-like strategic competence"
Build V2 with:
- persistent stacks
- eliminations
- chip-based scoring
- session-level opponent history
- explicit separation between custom-rule and poker-authentic tracks
