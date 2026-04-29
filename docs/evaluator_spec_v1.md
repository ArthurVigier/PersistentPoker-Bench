# Evaluator Specification v1

## Objective

This document defines the deterministic evaluation behavior for the first
PersistentPoker-Bench hand evaluator implementation.

## Card Universe

The evaluator receives a multiset of physical card instances composed of:

- 2 private hole cards for the player under evaluation
- 5 community cards
- 0 or more persistent pool cards

Duplicate exact cards are allowed because the persistent pool may contain repeated
community cards across prior hands.

## Global Evaluation Principle

- Categories are checked from strongest to weakest.
- The first matching category becomes the player's score.
- Tie-breaking is category-specific but always follows the global priority:
  1. duplicate-sensitive structure count
  2. card value strength
  3. split if still equal

## Category Definitions

### Double Royal Flush

- Requires 2 disjoint royal flushes from the available card multiset.
- A royal flush is `T J Q K A` of a single suit.
- The 2 royal flushes may share the same suit pattern or different suit patterns,
  but they may not reuse the same physical card instance unless that card exists
  as a duplicate instance in the multiset.

### Five of a Kind

- Requires at least 5 cards of the same rank.

### Double Straight Flush

- Requires 2 disjoint straight flushes from the available card multiset.
- A straight flush is any 5-card suited straight, including the wheel `A 2 3 4 5`.

### Royal Flush

- Requires at least 1 royal flush.

### Straight Flush

- Requires at least 1 straight flush.

### Four of a Kind + Flush

- Requires at least 1 rank with count >= 4 and at least 1 suit with count >= 5.
- The implementation does not require the flush cards to be disjoint from the
  four-of-a-kind structure for v1.

### Four of a Kind

- Requires at least 1 rank with count >= 4.

### Full House + Flush

- Requires a valid full house and a valid flush.
- The implementation does not require the flush cards to be disjoint from the
  full-house structure for v1.

### Flush

- Requires at least 5 cards of the same suit.

### Straight

- Requires 5 consecutive ranks regardless of suit, including the wheel.

### Three of a Kind

- Requires at least 1 rank with count >= 3.

### Two Pair

- Requires at least 2 distinct ranks with count >= 2.

### One Pair

- Requires at least 1 rank with count >= 2.

### High Card

- Always available.

## Tie-Break Defaults

The initial implementation uses the following deterministic comparison approach:

- `Double Royal Flush`: more disjoint royal flushes wins
- `Five of a Kind`: higher multiplicity, then higher rank
- `Double Straight Flush`: more disjoint straight flushes wins, then strongest
  straight-flush high cards
- `Royal Flush`: more available royal flush instances wins, then split
- `Straight Flush`: more disjoint straight flushes wins, then strongest high card
- `Four of a Kind + Flush`: stronger quads first, then stronger flush
- `Four of a Kind`: stronger quads first, then kickers
- `Full House + Flush`: stronger trips, then pair, then flush
- `Flush`: larger suit count, then top 5 flush cards
- `Straight`: higher straight
- `Three of a Kind`: larger trip count, then trip rank, then kickers
- `Two Pair`: stronger high pair, then low pair, then kicker
- `One Pair`: stronger pair, then kickers
- `High Card`: strongest top 5 cards

## Implementation Note

This evaluator is a benchmark-specific rules engine, not a standard poker
library. Determinism and auditability take priority over matching casino rules.

