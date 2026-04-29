# PersistentPoker-Bench Rules v1 (Option A)

## Scope

This document defines the official v1 benchmark rules for PersistentPoker-Bench.
It is intended to be stable, public, and citable by contributors, paper authors,
and benchmark users.

## Baseline Game Configuration

- Variant: No-Limit Texas Hold'em
- Player count: 4 by default
- Allowed range: 3 to 6 players
- Betting model: full no-limit
- Shared memory object: persistent public pool
- Winner decision after each hand: `reset` or `continue`
- Default action when omitted: `continue`

## Card State

Each hand includes:

- 2 private hole cards per player
- 5 public community cards
- 1 public persistent pool containing accumulated cards from prior hands

The persistent pool is public information at all times.

## Persistent Pool Lifecycle

1. The pool begins empty unless a scenario fixture specifies otherwise.
2. After each hand, only the 5 community cards are appended to the pool.
3. Duplicate cards are allowed in the pool representation and must be preserved.
4. The winner may choose:
   - `reset`: clear the pool before the next hand
   - `continue`: keep the pool for the next hand
5. If the winner does not provide a valid choice, the engine applies `continue`.

## Hand Construction Rule

The best hand is computed from all available cards:

- the player's 2 private cards
- the 5 community cards
- the full persistent pool

This differs from standard Hold'em because the pool may introduce duplicate ranks,
duplicate suits, or duplicate full card identities at the representation level.

For v1, hand categories are not limited to 5 total cards. Some categories explicitly
consume more than 5 physical card instances when they are evaluated.

## Official Hand Ranking

From strongest to weakest:

1. Double Royal Flush
2. Five of a Kind
3. Double Straight Flush
4. Royal Flush
5. Straight Flush
6. Four of a Kind + Flush
7. Four of a Kind
8. Full House + Flush
9. Flush
10. Straight
11. Three of a Kind
12. Two Pair
13. One Pair
14. High Card

## Tie-Breaking Rule

Tie-breaking priority is:

1. Higher duplicate count
2. Higher card values
3. Split pot if still perfectly tied

## Interpretive Notes for v1

The following points are normative for engine implementation:

- Duplicate count refers to the quantity of relevant matching cards that support
  the category under evaluation.
- `Double Royal Flush` requires 2 disjoint royal flush combinations from the
  available multiset of card instances. They may be from the same suit or from
  different suits.
- `Double Straight Flush` requires 2 disjoint straight flush combinations from the
  available multiset of card instances.
- For categories that combine structures, such as `Four of a Kind + Flush`,
  implementations must compare the duplicate-heavy structure first, then flush
  strength, unless a later clarification supersedes this note.
- Suit identity is not itself a tie-breaker unless a future version explicitly adds it.

## Remaining Clarifications To Lock In Before Tournament Freeze

These items should still be documented precisely before the first public tournament
release, even though the engine may proceed with deterministic defaults:

1. Exact comparison procedure for `Full House + Flush`
2. Exact comparison procedure for `Four of a Kind + Flush`
3. Exact transcript format for publishing hand-level evidence

## Benchmark Principle

If a rule ambiguity affects reproducibility, the engine must prefer explicit
deterministic behavior over poker realism.
