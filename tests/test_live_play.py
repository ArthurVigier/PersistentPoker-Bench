from persistentpoker_bench import HandRunnerConfig, HumanCommand, PlaySeatKind, PlaySeatSpec, PlaySessionConfig
from persistentpoker_bench.live_play import LiveMatchController
from persistentpoker_bench.schemas import WinnerPoolDecision


def test_live_match_controller_waits_for_human_then_completes() -> None:
    controller = LiveMatchController(
        PlaySessionConfig(
            seats=(
                PlaySeatSpec(name="You", kind=PlaySeatKind.HUMAN),
                PlaySeatSpec(name="CPU1", kind=PlaySeatKind.PASSIVE_BOT),
                PlaySeatSpec(name="CPU2", kind=PlaySeatKind.PASSIVE_BOT),
            ),
            hand_count=1,
            hand_runner_config=HandRunnerConfig(seed=20260428),
        )
    )

    controller.start()

    assert controller.waiting_for_human_seat == 0
    assert controller.legal_actions_for_human() is not None

    while not controller.finished:
        legal_actions = controller.legal_actions_for_human()
        assert legal_actions is not None
        controller.submit_human_action(
            HumanCommand(
                action="check" if legal_actions["can_check"] else "call",
                amount=None,
                winner_pool_decision=WinnerPoolDecision.CONTINUE,
            )
        )

    assert controller.finished is True
    assert len(controller.completed_results) == 1


def test_live_match_controller_replay_hands_exposes_completed_results() -> None:
    controller = LiveMatchController(
        PlaySessionConfig(
            seats=tuple(
                PlaySeatSpec(name=f"P{index + 1}", kind=PlaySeatKind.PASSIVE_BOT)
                for index in range(3)
            ),
            hand_count=1,
            hand_runner_config=HandRunnerConfig(seed=7),
        )
    )

    controller.start()

    assert controller.finished is True
    assert len(controller.replay_hands()) == 1
