# .agentic-pi/runtime/context_injector.py
"""Context injector for enriching agent prompts with relevant past learnings."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Tuple

# Configure logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# Constants
_MEMORY_ROOT = Path(__file__).resolve().parents[1] / "memory" / "durable"
_MAX_CARDS = 3


class ContextInjectorError(Exception):
    """Base exception for context injector errors."""


class GoalContractError(ContextInjectorError):
    """Raised when goal contract cannot be loaded or parsed."""


class MemoryCardReadError(ContextInjectorError):
    """Raised when a memory card cannot be read or parsed."""


def _load_goal_contract(run_id: str) -> Dict[str, Any]:
    """Load goal contract JSON for the given run."""
    contract_path = Path(__file__).resolve().parents[2] / ".agentic-runs" / run_id / "goal_contract.json"
    if not contract_path.is_file():
        raise GoalContractError(f"Goal contract not found at {contract_path}")
    try:
        return json.loads(contract_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise GoalContractError(f"Failed to parse goal contract: {exc}") from exc


def _collect_memory_cards() -> List[Dict[str, Any]]:
    """Recursively load all JSON memory cards under the durable memory root."""
    cards = []
    if not _MEMORY_ROOT.is_dir():
        logging.warning("Memory root not found: %s", _MEMORY_ROOT)
        return cards
    for json_path in _MEMORY_ROOT.rglob("*.json"):
        try:
            card = json.loads(json_path.read_text(encoding="utf-8"))
            # Ensure required fields exist
            for field in ("card_id", "content", "stored_at"):
                if field not in card:
                    raise MemoryCardReadError(f"Missing field {field} in {json_path}")
            cards.append(card)
        except Exception as exc:
            logging.warning("Skipping unreadable card %s: %s", json_path, exc)
    return cards


def _extract_keywords(goal_contract: Dict[str, Any]) -> List[str]:
    """Derive a list of keywords from the goal contract for relevance matching."""
    keywords = set()
    # raw_user_prompt may contain many words; split and lower
    raw = goal_contract.get("raw_user_prompt", "")
    for token in raw.split():
        token = token.strip(".,!?:;\"'()[]{}<>-_\n\t")
        if token:
            keywords.add(token.lower())
    # final_outputs contains list of file/artifact names
    outputs = goal_contract.get("final_outputs", [])
    if isinstance(outputs, list):
        for item in outputs:
            for token in str(item).split():
                token = token.strip(".,!?:;\"'()[]{}<>-_\n\t")
                if token:
                    keywords.add(token.lower())
    # done_criteria contains list of goal criteria phrases
    criteria = goal_contract.get("done_criteria", [])
    if isinstance(criteria, list):
        for item in criteria:
            for token in str(item).split():
                token = token.strip(".,!?:;\"'()[]{}<>-_\n\t")
                if token:
                    keywords.add(token.lower())
    return list(keywords)


def _score_card(card: Dict[str, Any], keywords: List[str]) -> Tuple[int, int]:
    """Score a memory card by keyword relevance and recency.

    Returns a tuple (relevance_score, recency_score) where higher relevance
    is better and higher recency (lower seconds) is better.
    """
    content = card.get("content", "")
    relevance = 0
    for kw in keywords:
        relevance += content.lower().count(kw)

    # Calculate recency in seconds from stored_at timestamp
    stored_at_str = card.get("stored_at", "")
    try:
        stored_dt = datetime.fromisoformat(stored_at_str)
        if stored_dt.tzinfo is None:
            stored_dt = stored_dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        recency = int((now - stored_dt).total_seconds())
    except (ValueError, TypeError):
        recency = 0  # treat missing/invalid timestamps as neutral

    return (relevance, -recency)  # negative recency so newer cards sort higher


def _format_context_block(selected_cards: List[Dict[str, Any]]) -> str:
    """Format selected memory cards into a CONTEXT block string.

    Each card content is truncated to 1000 characters to avoid bloat.
    """
    if not selected_cards:
        return ""

    lines = ["--- RELEVANT PAST LEARNINGS ---"]
    for i, card in enumerate(selected_cards):
        content = card.get("content", "").strip()
        if not content:
            continue
        if len(content) > 1000:
            content = content[:1000] + "..."
        if i > 0:
            lines.append("---")
        lines.append(content)
    lines.append("--- END RELEVANT PAST LEARNINGS ---")
    return "\n".join(lines)


def enrich_prompt_with_context(packet: dict, run_id: str) -> dict:
    """Load goal contract, scan durable memory cards, rank by relevance &
    recency, and prepend a CONTEXT section to a work packet's prompt.

    Args:
        packet: The work packet dictionary. Must contain a "prompt" key.
        run_id: The run ID used to locate the goal contract.

    Returns:
        The (possibly modified) packet. On any error, the original packet is
        returned unchanged and the error is logged.
    """
    try:
        # 1. Load the goal contract
        contract = _load_goal_contract(run_id)

        # 2. Extract keywords from the contract
        keywords = _extract_keywords(contract)
        if not keywords:
            logging.info("No keywords extracted from goal contract; returning original packet")
            return packet

        # 3. Collect memory cards
        cards = _collect_memory_cards()
        if not cards:
            logging.info("No memory cards found; returning original packet")
            return packet

        # 4. Filter out cards with empty/whitespace-only content
        valid_cards = [c for c in cards if c.get("content", "").strip()]
        if not valid_cards:
            logging.info("All memory cards have empty content; returning original packet")
            return packet

        # 5. Score and rank cards
        scored = []
        for card in valid_cards:
            relevance, recency = _score_card(card, keywords)
            scored.append((relevance, recency, card))

        # Sort by relevance desc, then recency desc (newer first)
        scored.sort(key=lambda x: (x[0], x[1]), reverse=True)

        # 6. Pick top cards
        top_cards = [item[2] for item in scored[:_MAX_CARDS]]

        # 7. Build context block
        context_block = _format_context_block(top_cards)
        if not context_block:
            logging.info("Generated empty context block; returning original packet")
            return packet

        # 8. Inject into prompt
        original_prompt = packet.get("prompt", "")
        if not original_prompt:
            logging.warning("Packet has no 'prompt' field; adding context as prompt")
            packet["prompt"] = context_block
        else:
            packet["prompt"] = context_block + "\n\n" + original_prompt

        logging.info(
            "Injected %d memory card(s) into prompt for run %s",
            len(top_cards), run_id,
        )
        return packet

    except ContextInjectorError as exc:
        logging.error("Context injector error: %s", exc)
        return packet
    except Exception as exc:
        logging.error("Unexpected error in context injector: %s", exc)
        return packet


def _cli_entry_point() -> None:
    """CLI entry point for manual testing.

    Usage:
        python context_injector.py <run_id> <packet_json_path>
    """
    import sys
    if len(sys.argv) < 3:
        print("Usage: python context_injector.py <run_id> <packet_json_path>")
        sys.exit(1)

    run_id = sys.argv[1]
    packet_path = Path(sys.argv[2])
    if not packet_path.is_file():
        print(f"Packet file not found: {packet_path}")
        sys.exit(1)

    try:
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"Failed to parse packet JSON: {exc}")
        sys.exit(1)

    result = enrich_prompt_with_context(packet, run_id)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    _cli_entry_point()
