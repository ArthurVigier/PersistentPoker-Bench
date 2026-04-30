import pytest

from persistentpoker_bench import WinnerPoolDecision, parse_llm_decision


def test_parse_llm_decision_accepts_strict_json() -> None:
    parsed = parse_llm_decision(
        '{"action":"call","amount":null,"believed_pool":["Ah","Kd"],"winner_pool_decision":"continue"}'
    )
    assert parsed.decision.action == "call"
    assert parsed.decision.believed_pool == ("Ah", "Kd")
    assert parsed.decision.winner_pool_decision is WinnerPoolDecision.CONTINUE


def test_parse_llm_decision_repairs_fenced_json() -> None:
    parsed = parse_llm_decision(
        """```json
        {
          action: 'raise',
          amount: 120,
          believed_pool: ['Ah', 'Kd', 'Ah'],
          winner_pool_decision: 'continue',
        }
        ```"""
    )
    assert parsed.decision.action == "raise"
    assert parsed.decision.amount == 120
    assert parsed.decision.believed_pool == ("Ah", "Kd", "Ah")


def test_parse_llm_decision_recovers_from_raw_text() -> None:
    parsed = parse_llm_decision(
        "Action: all_in\nAmount: 340\nBelieved_Pool: [Ah, Kd, Ah]\nWinner_Pool_Decision: reset"
    )
    assert parsed.parse_mode == "regex_fallback"
    assert parsed.decision.action == "all_in"
    assert parsed.decision.amount == 340
    assert parsed.decision.winner_pool_decision is WinnerPoolDecision.RESET


def test_parse_llm_decision_accepts_nested_market_action() -> None:
    parsed = parse_llm_decision(
        """
        {
          "action": "call",
          "amount": null,
          "market_action": {"type": "buy_card", "slot": 2},
          "believed_pool": ["Ah"],
          "winner_pool_decision": "continue"
        }
        """
    )

    assert parsed.decision.action == "call"
    assert parsed.decision.market_action == "buy_card"
    assert parsed.decision.market_slot == 2


def test_parse_llm_decision_accepts_flat_market_action() -> None:
    parsed = parse_llm_decision(
        """
        {
          "action": "check",
          "amount": null,
          "market_action": "pass_market",
          "market_slot": null,
          "believed_pool": [],
          "winner_pool_decision": "reset"
        }
        """
    )

    assert parsed.decision.action == "check"
    assert parsed.decision.market_action == "pass_market"
    assert parsed.decision.market_slot is None


def test_parse_llm_decision_rejects_missing_action() -> None:
    with pytest.raises(ValueError):
        parse_llm_decision("Believed_Pool: [Ah, Kd]")
