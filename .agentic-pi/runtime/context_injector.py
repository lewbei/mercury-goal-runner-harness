# .agentic-pi/runtime/context_injector.py
"""Context injector for enriching agent prompts with relevant past learnings."""

import importlib.util
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Tuple

# Configure logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# Constants
_MEMORY_ROOT = Path(__file__).resolve().parents[1] / "memory"
_ADAPTER_PATH = Path(__file__).resolve().parent / "mempalace_adapter.py"
_MAX_CARDS = 3
# Simple static stopword list -- extend as needed
_STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "if", "else", "for", "while",
    "write", "function", "to", "of", "in", "on", "as", "is", "are", "be", "by",
    "with", "from", "that", "this", "it", "its", "at", "not", "do", "does", "did",
    "has", "have", "had", "will", "shall", "should", "could", "would", "can", "may",
    "might", "must"
}


class ContextInjectorError(Exception):
    """Base exception for context injector errors."""


class GoalContractError(ContextInjectorError):
    """Raised when goal contract cannot be loaded or parsed."""


class MemoryCardReadError(ContextInjectorError):
    """Raised when a memory card cannot be read or parsed."""


#@ Requires(lambda run_id: isinstance(run_id, str), "run_id must be a string")
#@ Ensures(lambda result: isinstance(result, dict), "Result must be a dict")
def _load_goal_contract(run_id: str) -> Dict[str, Any]:
    """Load goal contract JSON for the given run.

    Args:
        run_id: Identifier of the run whose contract we need.

    Returns:
        Parsed contract dictionary.
    """
    contract_path = Path(__file__).resolve().parents[2] / ".agentic-runs" / run_id / "goal_contract.json"
    if not contract_path.is_file():
        raise GoalContractError(f"Goal contract not found at {contract_path}")
    try:
        return json.loads(contract_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise GoalContractError(f"Failed to parse goal contract: {exc}") from exc


def _load_adapter():
    spec = importlib.util.spec_from_file_location("mempalace_adapter", _ADAPTER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


#@ Requires(lambda: True, "No preconditions")
#@ Ensures(lambda cards: isinstance(cards, list), "Result must be a list of cards")
def _collect_memory_cards() -> List[Dict[str, Any]]:
    """Load gated durable MemPalace JSONL cards."""
    if not _MEMORY_ROOT.is_dir():
        logging.warning("Memory root not found: %s", _MEMORY_ROOT)
        return []
    try:
        cards = _load_adapter().load_durable_cards(_MEMORY_ROOT)
    except Exception as exc:
        raise MemoryCardReadError(f"Failed to load durable memory cards: {exc}") from exc
    return [
        card for card in cards
        if card.get("authority_level") == "advisory_only"
        and card.get("can_certify_done") is False
        and card.get("card_status") not in {"deprecated", "rejected"}
        and str(card.get("content", "")).strip()
    ]


#@ Requires(lambda goal_contract: isinstance(goal_contract, dict), "goal_contract must be a dict")
#@ Ensures(lambda result: isinstance(result, list), "Result must be a list of keywords")
def _extract_keywords(goal_contract: Dict[str, Any]) -> List[str]:
    """Derive a list of keywords from the goal contract for relevance matching.

    Stopwords defined in ``_STOPWORDS`` are filtered out.
    """
    keywords = set()
    # raw_user_prompt may contain many words; split and lower
    raw = goal_contract.get("raw_user_prompt", "")
    for token in raw.split():
        token = token.strip(".,!?:;\"'()[]{}<>-_\n\t")
        low = token.lower()
        if low and low not in _STOPWORDS:
            keywords.add(low)
    # final_outputs contains list of file/artifact names
    outputs = goal_contract.get("final_outputs", [])
    if isinstance(outputs, list):
        for item in outputs:
            for token in str(item).split():
                token = token.strip(".,!?:;\"'()[]{}<>-_\n\t")
                low = token.lower()
                if low and low not in _STOPWORDS:
                    keywords.add(low)
    # done_criteria contains list of goal criteria phrases
    criteria = goal_contract.get("done_criteria", [])
    if isinstance(criteria, list):
        for item in criteria:
            for token in str(item).split():
                token = token.strip(".,!?:;\"'()[]{}<>-_\n\t")
                low = token.lower()
                if low and low not in _STOPWORDS:
                    keywords.add(low)
    return list(keywords)


#@ Requires(lambda card: isinstance(card, dict), "card must be a dict")
#@ Requires(lambda keywords: isinstance(keywords, list), "keywords must be a list")
#@ Ensures(lambda result: isinstance(result, tuple) and len(result) == 2, "Result must be a (relevance, recency) tuple")
def _score_card(card: Dict[str, Any], keywords: List[str]) -> Tuple[int, int]:
    """Score a memory card by keyword relevance and recency.

    A card is considered relevant only when it contains **two or more** keyword matches.
    Returns a tuple (relevance_score, recency_score) where higher relevance is better
    and higher recency (lower seconds) is better.
    """
    content = card.get("content", "")
    # Count keyword occurrences
    matches = sum(content.lower().count(kw) for kw in keywords)
    # Enforce minimum of 2 matches
    relevance = matches if matches >= 2 else 0

    # Calculate recency in seconds from created_at/promoted_at timestamp
    stored_at_str = card.get("promoted_at") or card.get("created_at", "")
    try:
        stored_dt = datetime.fromisoformat(stored_at_str)
        if stored_dt.tzinfo is None:
            stored_dt = stored_dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        recency = int((now - stored_dt).total_seconds())
    except (ValueError, TypeError):
        recency = 0  # treat missing/invalid timestamps as neutral

    return (relevance, -recency)  # negative recency so newer cards sort higher


#@ Requires(lambda selected_cards: isinstance(selected_cards, list), "selected_cards must be a list")
#@ Ensures(lambda result: isinstance(result, str), "Result must be a string")
def _format_context_block(selected_cards: List[Dict[str, Any]]) -> str:
    """Format selected memory cards into a CONTEXT block string.

    Each card content is truncated to 1000 characters to avoid bloat.
    """
    if not selected_cards:
        return ""

    lines = ["--- RELEVANT ADVISORY MEMORY (NOT CERTIFICATION) ---"]
    for i, card in enumerate(selected_cards):
        content = card.get("content", "").strip()
        if not content:
            continue
        if len(content) > 1000:
            content = content[:1000] + "..."
        if i > 0:
            lines.append("---")
        lines.append(content)
    lines.append("--- END RELEVANT ADVISORY MEMORY ---")
    return "\n".join(lines)


#@ Requires(lambda packet: isinstance(packet, dict), "packet must be a dict")
#@ Requires(lambda run_id: isinstance(run_id, str), "run_id must be a string")
#@ Ensures(lambda result: isinstance(result, dict), "Result must be a dict (the enriched packet)")
def enrich_prompt_with_context(packet: dict, run_id: str) -> dict:
    """Load goal contract, scan gated durable memory cards, rank by relevance & recency,
    and prepend a CONTEXT section to a work packet's prompt.

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

        # 6. Pick top cards (only those with relevance > 0 will survive due to scoring rule)
        top_cards = [item[2] for item in scored[:_MAX_CARDS] if item[0] > 0]

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


#@ Requires(lambda: True, "No preconditions")
#@ Ensures(lambda: True, "No return value")
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

    # Write the enriched packet to the runtime directory using a deterministic name
    output_path = Path(__file__).resolve().parent / f"enriched_packet_{run_id}.json"
    try:
        output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Enriched packet written to {output_path}")
    except Exception as exc:
        print(f"Failed to write enriched packet: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    _cli_entry_point()
