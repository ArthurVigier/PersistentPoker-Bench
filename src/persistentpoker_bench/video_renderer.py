from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

from matplotlib import animation
from matplotlib import pyplot as plt
from matplotlib import patches

REPLAY_FORMAT = "persistentpoker-bench-replay-v1"

CARD_W = 0.62
CARD_H = 0.88


@dataclass(frozen=True, slots=True)
class VideoHand:
    hand_id: str
    variant: str
    winner_pool_decision: str
    replay_hand: dict[str, Any] | None
    events: tuple[dict[str, Any], ...]


@dataclass(frozen=True, slots=True)
class VideoMatch:
    label: str
    lineup_id: str | None
    track: str | None
    seed: int | None
    entrants: tuple[str, ...]
    metrics: dict[str, Any]
    final_pool: tuple[str, ...]
    final_stacks: tuple[int, ...]
    mode: str
    hands: tuple[VideoHand, ...]


@dataclass(frozen=True, slots=True)
class VideoProject:
    title: str
    source_path: str
    matches: tuple[VideoMatch, ...]


@dataclass(frozen=True, slots=True)
class VideoScene:
    kind: str
    match_index: int | None = None
    hand_index: int | None = None
    event_index: int | None = None


def render_video_from_source(
    *,
    input_path: str | Path,
    output_path: str | Path,
    fps: int = 2,
    mode: str = "auto",
    title: str | None = None,
) -> Path:
    project = load_video_project(input_path=input_path, mode=mode, title=title)
    scenes = build_video_scenes(project, fps=fps)
    if not scenes:
        raise ValueError("No scenes could be generated from the selected input.")

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    fig = plt.figure(figsize=(16, 9), facecolor="#071019")

    def update(frame_index: int) -> list[Any]:
        fig.clf()
        scene = scenes[frame_index]
        draw_scene(fig, project, scene, frame_index=frame_index, frame_count=len(scenes))
        return []

    movie = animation.FuncAnimation(
        fig,
        update,
        frames=len(scenes),
        interval=max(int(1000 / max(fps, 1)), 1),
        blit=False,
        repeat=False,
    )

    suffix = destination.suffix.lower()
    if suffix == ".gif":
        movie.save(destination, writer=animation.PillowWriter(fps=fps))
    else:
        try:
            movie.save(
                destination,
                writer=animation.FFMpegWriter(
                    fps=fps,
                    metadata={"artist": "PersistentPoker-Bench"},
                    bitrate=3200,
                ),
            )
        except Exception:
            fallback = destination.with_suffix(".gif")
            movie.save(fallback, writer=animation.PillowWriter(fps=fps))
            destination = fallback
    plt.close(fig)
    return destination


def load_video_project(
    *,
    input_path: str | Path,
    mode: str = "auto",
    title: str | None = None,
) -> VideoProject:
    source = Path(input_path)
    resolved_source = _resolve_input_path(source)
    matches = _load_matches_from_source(resolved_source, requested_mode=mode)
    project_title = title or resolved_source.stem.replace("-", " ").replace("_", " ").title()
    return VideoProject(
        title=project_title,
        source_path=str(resolved_source),
        matches=tuple(matches),
    )


def build_video_scenes(project: VideoProject, *, fps: int) -> list[VideoScene]:
    intro_frames = max(fps * 2, 2)
    hold_frames = max(fps, 1)
    scenes: list[VideoScene] = [VideoScene(kind="project_intro") for _ in range(intro_frames)]

    for match_index, match in enumerate(project.matches):
        scenes.extend(VideoScene(kind="match_intro", match_index=match_index) for _ in range(hold_frames))
        for hand_index, hand in enumerate(match.hands):
            if match.mode == "rich_action":
                for event_index in range(len(hand.events)):
                    scenes.append(
                        VideoScene(
                            kind="rich_action",
                            match_index=match_index,
                            hand_index=hand_index,
                            event_index=event_index,
                        )
                    )
            elif match.mode == "rich_hand":
                scenes.extend(
                    VideoScene(kind="rich_hand", match_index=match_index, hand_index=hand_index)
                    for _ in range(hold_frames)
                )
            else:
                for event_index in range(len(hand.events)):
                    scenes.append(
                        VideoScene(
                            kind="legacy_action",
                            match_index=match_index,
                            hand_index=hand_index,
                            event_index=event_index,
                        )
                    )
        scenes.extend(VideoScene(kind="match_outro", match_index=match_index) for _ in range(hold_frames))

    return scenes


def draw_scene(
    fig,
    project: VideoProject,
    scene: VideoScene,
    *,
    frame_index: int,
    frame_count: int,
) -> None:
    base_ax = fig.add_axes([0, 0, 1, 1])
    base_ax.set_xlim(0, 16)
    base_ax.set_ylim(0, 9)
    base_ax.axis("off")
    base_ax.set_facecolor("#071019")

    _draw_background(base_ax)
    _draw_header(base_ax, project, frame_index=frame_index, frame_count=frame_count)

    if scene.kind == "project_intro":
        _draw_project_intro(base_ax, project)
        return

    assert scene.match_index is not None
    match = project.matches[scene.match_index]
    _draw_match_badges(base_ax, match)

    if scene.kind == "match_intro":
        _draw_match_intro(base_ax, match)
        return
    if scene.kind == "match_outro":
        _draw_match_outro(base_ax, match)
        return

    assert scene.hand_index is not None
    hand = match.hands[scene.hand_index]

    if scene.kind == "rich_hand":
        _draw_rich_hand_scene(base_ax, match, hand, hand_number=scene.hand_index + 1)
        return

    assert scene.event_index is not None
    if scene.kind == "rich_action":
        _draw_rich_action_scene(
            base_ax,
            match,
            hand,
            hand_number=scene.hand_index + 1,
            event_index=scene.event_index,
        )
        return

    _draw_legacy_action_scene(
        fig,
        base_ax,
        match,
        hand,
        hand_number=scene.hand_index + 1,
        event_index=scene.event_index,
    )


def _resolve_input_path(path: Path) -> Path:
    if path.is_dir():
        for candidate_name in ("run_summary.json", "results.jsonl", "play_replay.json", "replay.json"):
            candidate = path / candidate_name
            if candidate.exists():
                return candidate
        raise FileNotFoundError(f"No supported input found in directory: {path}")
    if not path.exists():
        raise FileNotFoundError(f"Input not found: {path}")
    return path


def _load_matches_from_source(path: Path, *, requested_mode: str) -> list[VideoMatch]:
    if path.name == "run_summary.json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        artifacts = payload.get("artifacts", {})
        results_ref = artifacts.get("results_jsonl")
        if not isinstance(results_ref, str):
            raise ValueError("run_summary.json does not expose a results_jsonl artifact.")
        results_path = Path(results_ref)
        if not results_path.is_absolute():
            results_path = (path.parent / results_path).resolve()
        return _load_matches_from_results(results_path, requested_mode=requested_mode)

    if path.suffix.lower() == ".jsonl":
        if path.name == "decision_traces.jsonl":
            rows = _read_jsonl(path)
            return [_build_legacy_match_from_trace_rows(rows, label=path.parent.name or path.stem, requested_mode=requested_mode)]
        return _load_matches_from_results(path, requested_mode=requested_mode)

    payload = json.loads(path.read_text(encoding="utf-8"))
    if path.name.endswith("replay.json") or payload.get("format") == REPLAY_FORMAT:
        return [_build_match_from_replay_payload(payload, label=path.stem, requested_mode=requested_mode)]
    if "artifacts" in payload:
        return _load_matches_from_source(path, requested_mode=requested_mode)
    raise ValueError(f"Unsupported video input: {path}")


def _load_matches_from_results(path: Path, *, requested_mode: str) -> list[VideoMatch]:
    documents = _read_jsonl(path)
    matches: list[VideoMatch] = []
    for index, document in enumerate(documents):
        if not isinstance(document, dict):
            continue
        label = str(document.get("lineup_id") or document.get("label") or f"{path.parent.name}-match-{index + 1}")
        if isinstance(document.get("replay"), dict):
            matches.append(
                _build_match_from_results_document_with_replay(document, label=label, requested_mode=requested_mode)
            )
            continue
        if document.get("format") == REPLAY_FORMAT:
            matches.append(_build_match_from_replay_payload(document, label=label, requested_mode=requested_mode))
            continue
        transcript = tuple(row for row in document.get("transcript", []) if isinstance(row, dict))
        if transcript and any(isinstance(row.get("game_snapshot"), dict) for row in transcript):
            matches.append(
                _build_match_from_snapshot_transcript(document, transcript=transcript, label=label, requested_mode=requested_mode)
            )
            continue
        matches.append(
            _build_legacy_match_from_results_document(document, transcript=transcript, label=label, requested_mode=requested_mode)
        )
    return matches


def _build_match_from_results_document_with_replay(
    payload: dict[str, Any],
    *,
    label: str,
    requested_mode: str,
) -> VideoMatch:
    replay_payload = dict(payload["replay"])
    replay_payload.setdefault("label", label)
    match = _build_match_from_replay_payload(replay_payload, label=label, requested_mode=requested_mode)
    return VideoMatch(
        label=match.label,
        lineup_id=str(payload.get("lineup_id")) if payload.get("lineup_id") is not None else None,
        track=str(payload.get("track")) if payload.get("track") is not None else match.track,
        seed=_safe_int(payload.get("seed"), fallback=match.seed),
        entrants=tuple(_entrant_names(payload) or match.entrants),
        metrics=dict(payload.get("metrics", {})),
        final_pool=tuple(str(card) for card in payload.get("final_pool", [])),
        final_stacks=tuple(_safe_int(value, fallback=0) for value in payload.get("final_stacks", [])),
        mode=match.mode,
        hands=match.hands,
    )


def _build_match_from_replay_payload(
    payload: dict[str, Any],
    *,
    label: str,
    requested_mode: str,
) -> VideoMatch:
    hands = []
    rich_action_available = False
    for hand_payload in payload.get("hands", []):
        if not isinstance(hand_payload, dict):
            continue
        events = tuple(row for row in hand_payload.get("transcript", []) if isinstance(row, dict))
        rich_action_available = rich_action_available or any(isinstance(row.get("game_snapshot"), dict) for row in events)
        hands.append(
            VideoHand(
                hand_id=str(hand_payload.get("hand_id", f"hand-{len(hands) + 1:06d}")),
                variant=str(hand_payload.get("variant", "holdem")),
                winner_pool_decision=str(hand_payload.get("winner_pool_decision", "continue")),
                replay_hand=hand_payload,
                events=events,
            )
        )

    mode = "rich_action" if rich_action_available else "rich_hand"
    if requested_mode in {"action", "hand"}:
        mode = "rich_action" if requested_mode == "action" and rich_action_available else "rich_hand"

    return VideoMatch(
        label=str(payload.get("label", label)),
        lineup_id=None,
        track=str(payload.get("track")) if payload.get("track") is not None else None,
        seed=_safe_int((payload.get("session") or {}).get("seed"), fallback=None),
        entrants=tuple(str(name) for name in payload.get("player_names", [])),
        metrics={},
        final_pool=tuple(str(card) for card in ((hands[-1].replay_hand or {}).get("persistent_pool_after", []) if hands else [])),
        final_stacks=tuple(_safe_int(value, fallback=0) for value in ((hands[-1].replay_hand or {}).get("ending_stacks_snapshot", []) if hands else [])),
        mode=mode,
        hands=tuple(hands),
    )


def _build_match_from_snapshot_transcript(
    payload: dict[str, Any],
    *,
    transcript: tuple[dict[str, Any], ...],
    label: str,
    requested_mode: str,
) -> VideoMatch:
    grouped = _group_events_by_hand(transcript)
    hands: list[VideoHand] = []
    for hand_id, events in grouped:
        final_snapshot_event = next(
            (event for event in reversed(events) if isinstance(event.get("game_snapshot"), dict)),
            events[-1],
        )
        snapshot = dict(final_snapshot_event.get("game_snapshot", {}))
        replay_hand = {
            "hand_id": hand_id,
            "variant": snapshot.get("variant", "holdem"),
            "pot_total": snapshot.get("pot_total", 0),
            "community_cards": list(snapshot.get("community_cards", [])),
            "persistent_pool_before": list(snapshot.get("persistent_pool", [])),
            "persistent_pool_after": list(snapshot.get("persistent_pool", [])),
            "winner_pool_decision": str(events[-1].get("winner_pool_decision", "continue")),
            "players": [dict(player) for player in snapshot.get("players", []) if isinstance(player, dict)],
            "transcript": list(events),
        }
        hands.append(
            VideoHand(
                hand_id=hand_id,
                variant=str(replay_hand["variant"]),
                winner_pool_decision=str(replay_hand["winner_pool_decision"]),
                replay_hand=replay_hand,
                events=events,
            )
        )

    mode = "rich_action" if requested_mode != "hand" else "rich_hand"
    return VideoMatch(
        label=label,
        lineup_id=str(payload.get("lineup_id")) if payload.get("lineup_id") is not None else None,
        track=str(payload.get("track")) if payload.get("track") is not None else None,
        seed=_safe_int(payload.get("seed"), fallback=None),
        entrants=tuple(_entrant_names(payload)),
        metrics=dict(payload.get("metrics", {})),
        final_pool=tuple(str(card) for card in payload.get("final_pool", [])),
        final_stacks=tuple(_safe_int(value, fallback=0) for value in payload.get("final_stacks", [])),
        mode=mode,
        hands=tuple(hands),
    )


def _build_legacy_match_from_results_document(
    payload: dict[str, Any],
    *,
    transcript: tuple[dict[str, Any], ...],
    label: str,
    requested_mode: str,
) -> VideoMatch:
    grouped = _group_events_by_hand(transcript)
    hands = tuple(
        VideoHand(
            hand_id=hand_id,
            variant=_infer_variant_from_events(events),
            winner_pool_decision=str(events[-1].get("winner_pool_decision", "continue")) if events else "continue",
            replay_hand=None,
            events=events,
        )
        for hand_id, events in grouped
    )
    return VideoMatch(
        label=label,
        lineup_id=str(payload.get("lineup_id")) if payload.get("lineup_id") is not None else None,
        track=str(payload.get("track")) if payload.get("track") is not None else None,
        seed=_safe_int(payload.get("seed"), fallback=None),
        entrants=tuple(_entrant_names(payload)),
        metrics=dict(payload.get("metrics", {})),
        final_pool=tuple(str(card) for card in payload.get("final_pool", [])),
        final_stacks=tuple(_safe_int(value, fallback=0) for value in payload.get("final_stacks", [])),
        mode="legacy_action" if requested_mode == "auto" else "legacy_action",
        hands=hands,
    )


def _build_legacy_match_from_trace_rows(
    rows: list[dict[str, Any]],
    *,
    label: str,
    requested_mode: str,
) -> VideoMatch:
    grouped = _group_events_by_hand(tuple(rows))
    entrants = tuple(sorted({str(row.get("player_name")) for row in rows if row.get("player_name")}))
    hands = tuple(
        VideoHand(
            hand_id=hand_id,
            variant=_infer_variant_from_events(events),
            winner_pool_decision=str(events[-1].get("winner_pool_decision", "continue")) if events else "continue",
            replay_hand=None,
            events=events,
        )
        for hand_id, events in grouped
    )
    return VideoMatch(
        label=label,
        lineup_id=None,
        track=str(rows[0].get("track")) if rows and rows[0].get("track") is not None else None,
        seed=_safe_int(rows[0].get("seed"), fallback=None) if rows else None,
        entrants=entrants,
        metrics={},
        final_pool=(),
        final_stacks=(),
        mode="legacy_action" if requested_mode in {"auto", "action", "hand"} else "legacy_action",
        hands=hands,
    )


def _read_jsonl(path: Path) -> list[Any]:
    documents: list[Any] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        documents.append(json.loads(stripped))
    return documents


def _group_events_by_hand(events: tuple[dict[str, Any], ...]) -> list[tuple[str, tuple[dict[str, Any], ...]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    ordered_ids: list[str] = []
    for event in events:
        hand_id = str(event.get("hand_id", "unknown"))
        if hand_id not in grouped:
            grouped[hand_id] = []
            ordered_ids.append(hand_id)
        grouped[hand_id].append(event)
    return [(hand_id, tuple(grouped[hand_id])) for hand_id in ordered_ids]


def _infer_variant_from_events(events: tuple[dict[str, Any], ...]) -> str:
    street_names = {str(event.get("street", "")) for event in events}
    if any("street" in street for street in street_names if street):
        return "horse / stud mix"
    return "holdem"


def _entrant_names(payload: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for entrant in payload.get("entrants", []):
        if not isinstance(entrant, dict):
            continue
        if entrant.get("seat_name") is not None:
            names.append(str(entrant["seat_name"]))
    return names


def _draw_background(ax) -> None:
    ax.add_patch(
        patches.Rectangle(
            (0, 0),
            16,
            9,
            facecolor="#071019",
            edgecolor="none",
        )
    )
    ax.add_patch(
        patches.Ellipse(
            (8, 8.8),
            13.5,
            5.5,
            facecolor=(0.10, 0.25, 0.40, 0.16),
            edgecolor="none",
        )
    )


def _draw_header(ax, project: VideoProject, *, frame_index: int, frame_count: int) -> None:
    ax.text(0.6, 8.45, project.title, color="#f4efe3", fontsize=24, fontweight="bold")
    ax.text(0.6, 8.08, Path(project.source_path).name, color="#91a5bb", fontsize=10)
    ax.text(
        15.35,
        8.38,
        f"Frame {frame_index + 1} / {frame_count}",
        color="#f2b84b",
        fontsize=11,
        ha="right",
        fontweight="bold",
    )


def _draw_match_badges(ax, match: VideoMatch) -> None:
    x = 0.6
    for value in (
        match.track.upper() if match.track else None,
        f"seed {match.seed}" if match.seed is not None else None,
        match.lineup_id,
    ):
        if not value:
            continue
        _pill(ax, x, 7.55, str(value))
        x += 0.18 * len(str(value)) + 0.72


def _draw_project_intro(ax, project: VideoProject) -> None:
    _panel(ax, (0.6, 1.15), 14.8, 6.2, face="#0b1622")
    ax.text(1.0, 6.6, "Benchmark Video Export", color="#f2b84b", fontsize=18, fontweight="bold")
    ax.text(
        1.0,
        5.95,
        "This render automatically chooses the best visualization mode per artifact.",
        color="#e6edf5",
        fontsize=13,
    )
    ax.text(
        1.0,
        5.25,
        f"Matches detected: {len(project.matches)}",
        color="#9eb0c4",
        fontsize=12,
    )
    modes = {}
    for match in project.matches:
        modes[match.mode] = modes.get(match.mode, 0) + 1
    y = 4.55
    for mode, count in modes.items():
        ax.text(1.0, y, f"- {mode}: {count}", color="#d7e2ee", fontsize=12)
        y -= 0.45
    ax.text(
        1.0,
        2.05,
        "Rich action mode shows a table state per decision. Legacy mode falls back to a polished action dashboard.",
        color="#88a0b7",
        fontsize=11,
    )


def _draw_match_intro(ax, match: VideoMatch) -> None:
    _panel(ax, (0.7, 1.05), 14.6, 6.25)
    ax.text(1.05, 6.45, match.label, color="#f4efe3", fontsize=22, fontweight="bold")
    ax.text(1.05, 5.85, f"Hands: {len(match.hands)}", color="#f2b84b", fontsize=13, fontweight="bold")
    ax.text(1.05, 5.35, "Players", color="#9eb0c4", fontsize=11)
    y = 4.95
    for entrant in match.entrants or ("Unknown lineup",):
        ax.text(1.15, y, f"- {entrant}", color="#e6edf5", fontsize=12)
        y -= 0.42
    summary_lines = [
        f"Render mode: {match.mode}",
        f"Average pool size: {_safe_float((match.metrics or {}).get('average_pool_size')):.2f}",
        f"Memory accuracy: {_safe_float((match.metrics or {}).get('memory_accuracy')):.3f}",
        f"Estimated total cost: ${_safe_float((match.metrics or {}).get('estimated_total_cost')):.4f}",
    ]
    y = 4.95
    for line in summary_lines:
        ax.text(8.4, y, line, color="#d7e2ee", fontsize=12)
        y -= 0.48


def _draw_match_outro(ax, match: VideoMatch) -> None:
    _panel(ax, (0.7, 1.05), 14.6, 6.25)
    ax.text(1.05, 6.45, f"{match.label} summary", color="#f4efe3", fontsize=22, fontweight="bold")
    ax.text(1.05, 5.75, "Win counts", color="#9eb0c4", fontsize=11)
    win_counts = (match.metrics or {}).get("win_counts", {})
    y = 5.25
    for entrant in match.entrants:
        ax.text(1.15, y, f"- {entrant}: {win_counts.get(entrant, 0)}", color="#e6edf5", fontsize=12)
        y -= 0.42
    ax.text(8.4, 5.75, "Final pool", color="#9eb0c4", fontsize=11)
    ax.text(8.4, 5.25, " ".join(match.final_pool) or "-", color="#f2b84b", fontsize=12)
    if match.final_stacks:
        ax.text(8.4, 4.55, "Final stacks", color="#9eb0c4", fontsize=11)
        y = 4.08
        for entrant, stack in zip(match.entrants, match.final_stacks, strict=False):
            ax.text(8.5, y, f"- {entrant}: {stack}", color="#e6edf5", fontsize=12)
            y -= 0.4


def _draw_rich_hand_scene(ax, match: VideoMatch, hand: VideoHand, *, hand_number: int) -> None:
    replay_hand = hand.replay_hand or {}
    players = [dict(player) for player in replay_hand.get("players", []) if isinstance(player, dict)]
    community_cards = [str(card) for card in replay_hand.get("community_cards", [])]
    board_pool = [str(card) for card in replay_hand.get("persistent_pool_after", [])]
    _draw_table(ax, players=players, community_cards=community_cards, persistent_pool=board_pool, pot_total=_safe_int(replay_hand.get("pot_total"), fallback=0))
    _draw_side_panel(
        ax,
        title=f"Hand {hand_number}: {hand.hand_id}",
        lines=[
            f"Variant: {hand.variant.upper()}",
            f"Winner pool decision: {hand.winner_pool_decision}",
            f"Visible players: {len(players)}",
            f"Actions recorded: {len(hand.events)}",
        ],
        actions=hand.events[-6:],
    )


def _draw_rich_action_scene(
    ax,
    match: VideoMatch,
    hand: VideoHand,
    *,
    hand_number: int,
    event_index: int,
) -> None:
    event = hand.events[event_index]
    snapshot = dict(event.get("game_snapshot", {}))
    players = [dict(player) for player in snapshot.get("players", []) if isinstance(player, dict)]
    community_cards = [str(card) for card in snapshot.get("community_cards", [])]
    persistent_pool = [str(card) for card in snapshot.get("persistent_pool", [])]
    _draw_table(
        ax,
        players=players,
        community_cards=community_cards,
        persistent_pool=persistent_pool,
        pot_total=_safe_int(snapshot.get("pot_total"), fallback=0),
        acting_seat=_safe_int(event.get("player_index"), fallback=None),
    )
    action = dict(event.get("executed_action", {}))
    amount = action.get("amount")
    action_text = str(action.get("action", "unknown"))
    if amount is not None:
        action_text = f"{action_text} {amount}"
    _draw_side_panel(
        ax,
        title=f"Hand {hand_number}: {hand.hand_id}",
        lines=[
            f"Street: {snapshot.get('street', event.get('street', '-'))}",
            f"Actor: {event.get('player_name', '-')}",
            f"Action: {action_text}",
            f"Memory accuracy: {_safe_float((event.get('memory') or {}).get('multiset_accuracy')):.2f}",
            f"Latency: {_safe_float(event.get('latency_seconds')):.2f}s",
            f"Winner pool vote: {event.get('winner_pool_decision', '-')}",
        ],
        actions=hand.events[max(0, event_index - 5) : event_index + 1],
        highlight_index=len(hand.events[max(0, event_index - 5) : event_index + 1]) - 1,
    )


def _draw_legacy_action_scene(
    fig,
    ax,
    match: VideoMatch,
    hand: VideoHand,
    *,
    hand_number: int,
    event_index: int,
) -> None:
    event = hand.events[event_index]
    _panel(ax, (0.65, 0.9), 9.6, 6.1)
    _panel(ax, (10.55, 0.9), 4.8, 6.1)

    ax.text(1.0, 6.6, f"Hand {hand_number}: {hand.hand_id}", color="#f4efe3", fontsize=19, fontweight="bold")
    ax.text(1.0, 6.12, f"Track: {match.track or '-'}", color="#8ea4ba", fontsize=11)
    ax.text(1.0, 5.56, f"Current actor: {event.get('player_name', '-')}", color="#f2b84b", fontsize=16, fontweight="bold")

    action = dict(event.get("executed_action", {}))
    decision = dict(event.get("normalized_decision", {}))
    action_text = str(action.get("action", "unknown"))
    if action.get("amount") is not None:
        action_text = f"{action_text} {action.get('amount')}"
    ax.text(1.0, 4.95, f"Executed action: {action_text}", color="#dce7f2", fontsize=14)
    ax.text(1.0, 4.52, f"Street: {event.get('street', '-')}", color="#9eb0c4", fontsize=12)
    ax.text(1.0, 4.10, f"Pool belief size: {len(tuple(event.get('believed_pool', ()) or ())) }", color="#9eb0c4", fontsize=12)
    ax.text(1.0, 3.68, f"Winner pool vote: {event.get('winner_pool_decision', '-')}", color="#9eb0c4", fontsize=12)
    ax.text(1.0, 3.26, f"Parse mode: {event.get('parse_mode', '-')}", color="#9eb0c4", fontsize=12)
    ax.text(1.0, 2.84, f"Memory accuracy: {_safe_float((event.get('memory') or {}).get('multiset_accuracy')):.2f}", color="#9eb0c4", fontsize=12)
    ax.text(1.0, 2.42, f"Latency: {_safe_float(event.get('latency_seconds')):.2f}s", color="#9eb0c4", fontsize=12)

    chart_ax = fig.add_axes([0.09, 0.17, 0.49, 0.22], facecolor="#0b1622")
    chart_ax.spines[:].set_visible(False)
    chart_ax.tick_params(colors="#88a0b7", labelsize=8)
    chart_ax.grid(alpha=0.12, color="#88a0b7")
    xs = list(range(1, event_index + 2))
    ys = [len(tuple(item.get("believed_pool", ()) or ())) for item in hand.events[: event_index + 1]]
    chart_ax.plot(xs, ys, color="#66d4c5", linewidth=2.6)
    chart_ax.scatter(xs[-1], ys[-1], color="#f2b84b", s=40, zorder=3)
    chart_ax.set_title("Believed public pool size through this hand", color="#dce7f2", fontsize=10)
    chart_ax.set_xlim(1, max(xs[-1], 2))
    chart_ax.set_ylim(0, max(max(ys, default=0) + 1, 2))

    lines = [
        f"Players: {', '.join(match.entrants) or '-'}",
        f"Decision: {decision.get('action', '-')}",
        f"Cost est.: ${_safe_float((event.get('usage') or {}).get('estimated_cost')):.4f}",
        f"Prompt tokens: {_safe_int((event.get('usage') or {}).get('prompt_tokens'), fallback=0)}",
        f"Completion tokens: {_safe_int((event.get('usage') or {}).get('completion_tokens'), fallback=0)}",
    ]
    y = 6.35
    for line in lines:
        ax.text(10.9, y, line, color="#dce7f2", fontsize=11)
        y -= 0.48

    ax.text(10.9, 3.65, "Recent actions", color="#f2b84b", fontsize=13, fontweight="bold")
    recent = hand.events[max(0, event_index - 6) : event_index + 1]
    y = 3.2
    for offset, item in enumerate(recent):
        executed = dict(item.get("executed_action", {}))
        recent_text = f"{item.get('player_name', '-')}: {executed.get('action', '-')}"
        if executed.get("amount") is not None:
            recent_text += f" {executed.get('amount')}"
        color = "#f4efe3" if offset == len(recent) - 1 else "#96a8bc"
        ax.text(10.95, y, recent_text[:36], color=color, fontsize=10.5)
        y -= 0.38


def _draw_table(
    ax,
    *,
    players: list[dict[str, Any]],
    community_cards: list[str],
    persistent_pool: list[str],
    pot_total: int,
    acting_seat: int | None = None,
) -> None:
    table_bounds = (0.65, 0.9, 9.6, 6.1)
    _panel(ax, (table_bounds[0], table_bounds[1]), table_bounds[2], table_bounds[3])

    cx = 5.4
    cy = 3.95
    ax.add_patch(
        patches.Ellipse(
            (cx, cy),
            8.25,
            4.85,
            facecolor="#1d5f34",
            edgecolor="#4a2c1a",
            linewidth=14,
            zorder=2,
        )
    )
    ax.add_patch(
        patches.Ellipse(
            (cx, cy),
            7.95,
            4.55,
            facecolor="none",
            edgecolor=(1, 1, 1, 0.08),
            linewidth=2,
            zorder=3,
        )
    )

    ax.text(cx, 5.02, f"Pot {pot_total}", color="#f2b84b", fontsize=15, ha="center", fontweight="bold")
    _draw_card_row(ax, community_cards, center=(cx, 4.45), hidden=False)
    ax.text(cx, 3.55, "Persistent pool", color="#8ea4ba", fontsize=10, ha="center")
    _draw_card_row(ax, persistent_pool[-12:], center=(cx, 3.1), hidden=False, scale=0.78)

    player_count = max(len(players), 1)
    positions = _seat_positions(cx, cy, radius_x=3.45, radius_y=2.25, count=player_count)
    for index, player in enumerate(players):
        seat = _safe_int(player.get("seat"), fallback=index)
        px, py = positions[index]
        status = _player_status(player)
        border = "#f2b84b" if acting_seat is not None and seat == acting_seat else "#2e4154"
        alpha = 0.52 if status in {"folded", "eliminated"} else 0.96
        ax.add_patch(
            patches.FancyBboxPatch(
                (px - 0.9, py - 0.55),
                1.8,
                1.1,
                boxstyle="round,pad=0.03,rounding_size=0.12",
                facecolor=(0.04, 0.09, 0.14, alpha),
                edgecolor=border,
                linewidth=2.2,
                zorder=4,
            )
        )
        ax.text(px, py + 0.17, str(player.get("name", f"P{index + 1}"))[:18], color="#f4efe3", fontsize=10, ha="center", zorder=5)
        ax.text(px, py - 0.1, f"{_safe_int(player.get('stack'), fallback=0)} chips", color="#8ea4ba", fontsize=8.8, ha="center", zorder=5)
        ax.text(px, py - 0.33, status, color="#f2b84b" if status == "active" else "#ef8f8f", fontsize=8, ha="center", zorder=5)

        cards = [str(card) for card in player.get("hole_cards", [])] + [str(card) for card in player.get("up_cards", [])]
        if not cards:
            cards = ["??", "??"]
        _draw_card_row(ax, cards[:4], center=(px, py - 0.92), hidden=(status == "folded"), scale=0.72)


def _draw_side_panel(
    ax,
    *,
    title: str,
    lines: list[str],
    actions: tuple[dict[str, Any], ...] | list[dict[str, Any]],
    highlight_index: int | None = None,
) -> None:
    _panel(ax, (10.55, 0.9), 4.8, 6.1)
    ax.text(10.9, 6.55, title, color="#f4efe3", fontsize=16, fontweight="bold")
    y = 6.08
    for line in lines:
        ax.text(10.9, y, line, color="#dce7f2", fontsize=11.4)
        y -= 0.42
    ax.text(10.9, 3.5, "Recent actions", color="#f2b84b", fontsize=12.5, fontweight="bold")
    y = 3.08
    for index, event in enumerate(actions[-7:]):
        executed = dict(event.get("executed_action", {}))
        action_text = f"{event.get('player_name', '-')}: {executed.get('action', '-')}"
        if executed.get("amount") is not None:
            action_text += f" {executed.get('amount')}"
        color = "#f4efe3" if highlight_index is not None and index == highlight_index else "#95a8bb"
        ax.text(10.95, y, action_text[:38], color=color, fontsize=10.2)
        y -= 0.35


def _panel(ax, xy: tuple[float, float], width: float, height: float, face: str = "#0b1622") -> None:
    ax.add_patch(
        patches.FancyBboxPatch(
            xy,
            width,
            height,
            boxstyle="round,pad=0.05,rounding_size=0.18",
            facecolor=face,
            edgecolor=(0.95, 0.72, 0.29, 0.18),
            linewidth=1.4,
            zorder=1,
        )
    )


def _pill(ax, x: float, y: float, text: str) -> None:
    width = max(1.1, 0.12 * len(text) + 0.5)
    ax.add_patch(
        patches.FancyBboxPatch(
            (x, y),
            width,
            0.36,
            boxstyle="round,pad=0.03,rounding_size=0.18",
            facecolor="#0d2133",
            edgecolor=(0.95, 0.72, 0.29, 0.16),
            linewidth=1.0,
        )
    )
    ax.text(x + 0.15, y + 0.11, text, color="#f2b84b", fontsize=9.5, fontweight="bold")


def _draw_card_row(
    ax,
    cards: list[str],
    *,
    center: tuple[float, float],
    hidden: bool,
    scale: float = 1.0,
) -> None:
    if not cards:
        return
    x_center, y_center = center
    spacing = CARD_W * scale * 1.18
    total_w = spacing * (len(cards) - 1)
    start_x = x_center - total_w / 2
    for index, card in enumerate(cards):
        _draw_card(ax, start_x + index * spacing, y_center, card, hidden=hidden, scale=scale)


def _draw_card(ax, x: float, y: float, card: str, *, hidden: bool, scale: float) -> None:
    width = CARD_W * scale
    height = CARD_H * scale
    if hidden or card == "??":
        face = "#173147"
        edge = "#f2b84b"
        text = "?"
        color = "#f4efe3"
    else:
        face = "#fffaf1"
        edge = "#d8d8d8"
        rank, suit, color = _card_parts(card)
        text = f"{rank}{suit}"
    ax.add_patch(
        patches.FancyBboxPatch(
            (x - width / 2, y - height / 2),
            width,
            height,
            boxstyle="round,pad=0.02,rounding_size=0.08",
            facecolor=face,
            edgecolor=edge,
            linewidth=1.0,
            zorder=6,
        )
    )
    ax.text(x, y, text, color=color, fontsize=10 * scale, ha="center", va="center", zorder=7, fontweight="bold")


def _card_parts(card: str) -> tuple[str, str, str]:
    suit_icons = {"h": "♥", "d": "♦", "c": "♣", "s": "♠"}
    suit = suit_icons.get(card[-1].lower(), "?")
    color = "#c93a3a" if card[-1].lower() in {"h", "d"} else "#20242c"
    return card[:-1], suit, color


def _seat_positions(cx: float, cy: float, *, radius_x: float, radius_y: float, count: int) -> list[tuple[float, float]]:
    import math

    if count <= 1:
        return [(cx, cy - radius_y)]
    positions: list[tuple[float, float]] = []
    for index in range(count):
        angle = math.pi / 2 + (2 * math.pi * index / count)
        positions.append((cx + math.cos(angle) * radius_x, cy + math.sin(angle) * radius_y))
    return positions


def _player_status(player: dict[str, Any]) -> str:
    if bool(player.get("eliminated", False)):
        return "eliminated"
    if bool(player.get("folded", False)):
        return "folded"
    if bool(player.get("all_in", False)):
        return "all-in"
    return "active"


def _safe_int(value: Any, *, fallback: int | None) -> int | None:
    if value is None:
        return fallback
    try:
        return int(value)
    except Exception:
        return fallback


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0
