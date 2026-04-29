from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from persistentpoker_bench.cards import parse_cards
from persistentpoker_bench.schemas import LLMDecision, WinnerPoolDecision, normalize_decision_payload

JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.IGNORECASE | re.DOTALL)
CARD_TOKEN_RE = re.compile(r"\b([2-9TJQKA][cdhs])\b", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class ParsedDecision:
    decision: LLMDecision
    parse_mode: str
    raw_text: str
    parsed_payload: dict[str, Any]


def parse_llm_decision(raw_text: str) -> ParsedDecision:
    for parse_mode, candidate in _iter_candidate_payloads(raw_text):
        mapping = _parse_mapping(candidate)
        if mapping is None:
            continue
        decision = normalize_decision_payload(mapping)
        return ParsedDecision(
            decision=decision,
            parse_mode=parse_mode,
            raw_text=raw_text,
            parsed_payload=dict(mapping),
        )

    fallback_payload = _regex_fallback_payload(raw_text)
    decision = normalize_decision_payload(fallback_payload)
    return ParsedDecision(
        decision=decision,
        parse_mode="regex_fallback",
        raw_text=raw_text,
        parsed_payload=fallback_payload,
    )


def _iter_candidate_payloads(raw_text: str) -> Iterable[tuple[str, str]]:
    stripped = raw_text.strip()
    if stripped:
        yield "strict_json", stripped

    for match in JSON_BLOCK_RE.finditer(raw_text):
        yield "markdown_json", match.group(1).strip()

    for snippet in _extract_balanced_json_objects(raw_text):
        yield "balanced_object", snippet


def _parse_mapping(candidate: str) -> Mapping[str, Any] | None:
    parsed = _try_json_load(candidate)
    if isinstance(parsed, Mapping):
        return parsed

    repaired = _repair_json_text(candidate)
    if repaired != candidate:
        parsed = _try_json_load(repaired)
        if isinstance(parsed, Mapping):
            return parsed

    pythonic = _to_python_literal(candidate)
    if pythonic is not None and isinstance(pythonic, Mapping):
        return dict(pythonic)

    return None


def _try_json_load(candidate: str) -> Any:
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return None


def _repair_json_text(candidate: str) -> str:
    repaired = candidate.strip()
    repaired = repaired.replace("“", '"').replace("”", '"').replace("’", "'").replace("‘", "'")
    repaired = re.sub(r",(\s*[}\]])", r"\1", repaired)
    repaired = re.sub(r"([{,]\s*)([A-Za-z_][A-Za-z0-9_]*)(\s*:)", r'\1"\2"\3', repaired)
    repaired = re.sub(r":\s*'([^']*)'", lambda m: ': ' + json.dumps(m.group(1)), repaired)
    repaired = re.sub(r"'([A-Za-z_][A-Za-z0-9_]*)'\s*:", lambda m: json.dumps(m.group(1)) + ":", repaired)
    return repaired


def _to_python_literal(candidate: str) -> Any:
    pythonish = candidate.strip()
    pythonish = pythonish.replace("null", "None").replace("true", "True").replace("false", "False")
    try:
        return ast.literal_eval(pythonish)
    except (SyntaxError, ValueError):
        return None


def _extract_balanced_json_objects(raw_text: str) -> list[str]:
    objects: list[str] = []
    depth = 0
    start_index: int | None = None

    for index, char in enumerate(raw_text):
        if char == "{":
            if depth == 0:
                start_index = index
            depth += 1
        elif char == "}":
            if depth == 0:
                continue
            depth -= 1
            if depth == 0 and start_index is not None:
                objects.append(raw_text[start_index : index + 1].strip())
                start_index = None

    return objects


def _regex_fallback_payload(raw_text: str) -> dict[str, Any]:
    action_match = re.search(
        r"\b(action)\b\s*[:=]\s*['\"]?([a-z_]+)['\"]?",
        raw_text,
        flags=re.IGNORECASE,
    )
    if action_match is None:
        action_match = re.search(r"\b(fold|check|call|bet|raise|all_in)\b", raw_text, flags=re.IGNORECASE)
        if action_match is None:
            raise ValueError("Unable to recover action from model output.")
        action_value = action_match.group(1).lower()
    else:
        action_value = action_match.group(2).lower()

    amount_match = re.search(r"\bamount\b\s*[:=]\s*['\"]?(\d+)['\"]?", raw_text, flags=re.IGNORECASE)
    amount_value = int(amount_match.group(1)) if amount_match else None

    pool_match = re.search(
        r"\bbelieved_pool\b\s*[:=]\s*(\[[^\]]*\]|.+)",
        raw_text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    believed_pool = []
    if pool_match:
        believed_pool = _extract_card_tokens(pool_match.group(1))
    if not believed_pool:
        believed_pool = _extract_card_tokens(raw_text)
    parse_cards(believed_pool)

    winner_match = re.search(
        r"\bwinner_pool_decision\b\s*[:=]\s*['\"]?(reset|continue)['\"]?",
        raw_text,
        flags=re.IGNORECASE,
    )
    if winner_match:
        winner_pool_decision = winner_match.group(1).lower()
    else:
        reset_match = re.search(r"\b(reset|continue)\b", raw_text, flags=re.IGNORECASE)
        winner_pool_decision = (
            reset_match.group(1).lower()
            if reset_match
            else WinnerPoolDecision.CONTINUE.value
        )

    return {
        "action": action_value,
        "amount": amount_value,
        "believed_pool": believed_pool,
        "winner_pool_decision": winner_pool_decision,
    }


def _extract_card_tokens(text: str) -> list[str]:
    return [match.upper()[0] + match.lower()[1] for match in CARD_TOKEN_RE.findall(text)]

