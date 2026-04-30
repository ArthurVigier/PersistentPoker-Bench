from persistentpoker_bench import LLMDecision, PersistentPool, StaticDecisionAgent, WinnerPoolDecision, run_seeded_hand
from persistentpoker_bench.hand_runner import HandRunnerConfig
from persistentpoker_bench.wall_street import (
    BUY_CARD,
    PASS_MARKET,
    apply_market_action,
    create_wall_street_market,
    serialize_legal_market_actions,
    validate_or_fallback_market_action,
)


def _passive_decisions() -> list[LLMDecision]:
    return [
        LLMDecision("call", None, (), WinnerPoolDecision.CONTINUE),
        LLMDecision("call", None, (), WinnerPoolDecision.CONTINUE),
        LLMDecision("check", None, (), WinnerPoolDecision.CONTINUE),
        LLMDecision("check", None, (), WinnerPoolDecision.CONTINUE),
        LLMDecision("check", None, (), WinnerPoolDecision.CONTINUE),
        LLMDecision("check", None, (), WinnerPoolDecision.CONTINUE),
        LLMDecision("check", None, (), WinnerPoolDecision.CONTINUE),
        LLMDecision("check", None, (), WinnerPoolDecision.CONTINUE),
        LLMDecision("check", None, (), WinnerPoolDecision.CONTINUE),
        LLMDecision("check", None, (), WinnerPoolDecision.CONTINUE),
        LLMDecision("check", None, (), WinnerPoolDecision.CONTINUE),
        LLMDecision("check", None, (), WinnerPoolDecision.CONTINUE),
    ]


def test_wall_street_buy_updates_stack_pot_cards_and_row() -> None:
    from persistentpoker_bench import create_hand_state, standard_deck

    hand_state = create_hand_state(["A", "B", "C"], game_mode="horse_v3_wall_street", variant="holdem")
    deck = list(standard_deck())
    hand_state.deck = deck
    hand_state.wall_street_market = create_wall_street_market(deck, big_blind=20)
    first_slot_card = hand_state.wall_street_market.slots[0].card
    first_replacement = deck[0]

    legal = serialize_legal_market_actions(hand_state, 0)
    assert legal["can_buy_card"] is True
    assert legal["affordable_slots"] == [0, 1, 2, 3]

    result = apply_market_action(
        hand_state,
        0,
        validate_or_fallback_market_action(
            LLMDecision(
                "call",
                None,
                (),
                WinnerPoolDecision.CONTINUE,
                market_action=BUY_CARD,
                market_slot=0,
            ),
            hand_state,
            0,
        ),
    )

    assert result["type"] == BUY_CARD
    assert result["card"] == first_slot_card.to_notation()
    assert result["replacement_card"] == first_replacement.to_notation()
    assert hand_state.players[0].stack == 1980
    assert hand_state.pot_total == 50
    assert hand_state.players[0].market_cards == (first_slot_card,)
    assert hand_state.wall_street_market.slots[0].card == first_replacement


def test_wall_street_invalid_or_missing_action_passes() -> None:
    from persistentpoker_bench import create_hand_state, standard_deck

    hand_state = create_hand_state(["A", "B", "C"], game_mode="horse_v3_wall_street", variant="holdem")
    hand_state.deck = list(standard_deck())
    hand_state.wall_street_market = create_wall_street_market(hand_state.deck, big_blind=20)

    action = validate_or_fallback_market_action(
        LLMDecision("call", None, (), WinnerPoolDecision.CONTINUE, market_action=BUY_CARD, market_slot=99),
        hand_state,
        0,
    )

    assert action.action_type == PASS_MARKET


def test_run_seeded_v3_wall_street_hand_records_market_transcript() -> None:
    buyer_decisions = [
        LLMDecision(
            "call",
            None,
            (),
            WinnerPoolDecision.CONTINUE,
            market_action=BUY_CARD,
            market_slot=0,
        ),
        *_passive_decisions(),
    ]
    agents = {
        0: StaticDecisionAgent(buyer_decisions),
        1: StaticDecisionAgent(_passive_decisions() * 3),
        2: StaticDecisionAgent(_passive_decisions() * 3),
    }

    result = run_seeded_hand(
        player_names=["A", "B", "C"],
        decision_agents=agents,
        persistent_pool=PersistentPool(),
        config=HandRunnerConfig(seed=20260430, game_mode="horse_v3_wall_street"),
    )

    first_event = result.transcript[0]
    assert first_event["executed_market_action"]["type"] == BUY_CARD
    assert first_event["game_snapshot"]["market"]["wall_street"]
    assert first_event["legal_actions"]["market"]["can_buy_card"] is True
    assert result.hand_state.players[0].market_spend_total == 20
    assert result.hand_state.players[0].market_cards
    assert result.persistent_pool_after
