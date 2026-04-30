from persistentpoker_bench import (
    DEFAULT_MODEL_REGISTRY,
    EFFICIENCY_MODELS,
    FRONTIER_MODELS,
    LeaderboardTrack,
    models_for_track,
)


def test_frontier_and_efficiency_tracks_have_five_models_each() -> None:
    assert len(FRONTIER_MODELS) == 6
    assert len(EFFICIENCY_MODELS) == 6
    assert len(DEFAULT_MODEL_REGISTRY) == 12


def test_frontier_track_uses_current_shortlist() -> None:
    frontier_ids = tuple(model.model_id for model in FRONTIER_MODELS)
    assert frontier_ids == (
        "deepseek-v4-pro",
        "grok-4.20-reasoning",
        "qwen3-max",
        "gemini-3.1-pro",
        "gpt-5.5",
        "mistral-large-latest",
    )


def test_models_for_track_filters_correctly() -> None:
    assert models_for_track(LeaderboardTrack.FRONTIER) == FRONTIER_MODELS
    assert models_for_track(LeaderboardTrack.EFFICIENCY) == EFFICIENCY_MODELS
