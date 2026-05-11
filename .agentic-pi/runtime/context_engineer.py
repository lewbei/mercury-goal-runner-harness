# .agentic-pi/runtime/context_engineer.py
"""Extended context engineering with freshness, usage tracking and criticality ordering.
"""

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Set, Tuple

# Local imports – keep the original injector unchanged
import context_injector
import smart_memory

# ---------------------------------------------------------------------------
# Constants & logger
# ---------------------------------------------------------------------------
LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)

STATE_PATH = Path(__file__).resolve().parents[2] / ".agentic-pi" / "runtime" / "context_state.json"
USAGE_REPORT_DIR = Path(__file__).resolve().parents[2] / ".agentic-pi" / "runtime"

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------
class ContextEngineerError(Exception):
    """Base class for context‑engineer errors."""

class StateLoadError(ContextEngineerError):
    """Raised when `context_state.json` cannot be read or parsed."""

class UsageTrackingError(ContextEngineerError):
    """Raised when usage tracking fails."""

# ---------------------------------------------------------------------------
# Helper functions – state handling
# ---------------------------------------------------------------------------
def _load_context_state() -> Dict[str, List[str]]:
    """Load the JSON file that maps `run_id` → list of `card_id` already injected.

    Returns an empty dict if the file does not exist.
    """
    if not STATE_PATH.is_file():
        LOGGER.info("Context state file not found, starting fresh.")
        return {}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        raise StateLoadError(f"Failed to load context state: {exc}") from exc


def _save_context_state(state: Dict[str, List[str]]) -> None:
    """Write the `state` mapping back to `context_state.json`."""
    try:
        STATE_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as exc:
        LOGGER.error("Unable to persist context state: %s", exc)

# ---------------------------------------------------------------------------
# Freshness utilities
# ---------------------------------------------------------------------------
def _filter_fresh_cards(all_cards: List[Dict[str, Any]], seen_ids: Set[str], run_id: str) -> List[Dict[str, Any]]:
    """Return only cards that have **not** been seen in any previous run.

    For each returned card we add a `"seen_since_run"` field set to the current `run_id`.
    """
    fresh: List[Dict[str, Any]] = []
    for card in all_cards:
        cid = card.card_id
        if not cid:
            continue
        if cid in seen_ids:
            continue
        # Mark as newly seen for this run
        card.seen_since_run = run_id
        fresh.append(card)
    return fresh

# ---------------------------------------------------------------------------
# Criticality ordering utilities
# ---------------------------------------------------------------------------
def _load_success_card_ids() -> Set[str]:
    """Parse all historic `injection_quality.json` files and collect card IDs that contributed to a successful run.

    The file format (from `smart_memory.record_injection_quality`) contains a list `used_card_ids` and a boolean `success`.
    """
    success_ids: Set[str] = set()
    # Search all previous runs under `.agentic-runs`
    base = Path(__file__).resolve().parents[2] / ".agentic-runs"
    for run_dir in base.iterdir():
        if not run_dir.is_dir():
            continue
        iq_path = run_dir / "injection_quality.json"
        if not iq_path.is_file():
            continue
        try:
            data = json.loads(iq_path.read_text(encoding="utf-8"))
            if data.get("success") and isinstance(data.get("used_card_ids"), list):
                success_ids.update(data["used_card_ids"])
        except Exception:
            LOGGER.debug("Skipping malformed injection_quality at %s", iq_path)
    return success_ids


def _score_relevance(card: Dict[str, Any], keywords: List[str]) -> float:
    """Simple relevance: fraction of keywords present in the card content (case‑insensitive)."""
    if not keywords:
        return 0.0
    content = card.content.lower()
    matches = sum(1 for kw in keywords if kw.lower() in content)
    return matches / len(keywords)


def _tier_cards(cards: List[Dict[str, Any]], success_ids: Set[str], keywords: List[str]) -> List[Dict[str, Any]]:
    """Return a list ordered by criticality tiers.

    Tier 1 – cards in `success_ids`.
    Tier 2 – cards with relevance >= 0.6.
    Tier 3 – the rest.
    Within each tier we sort by `stored_at` descending (newest first).
    """
    tier1, tier2, tier3 = [], [], []
    for card in cards:
        cid = card.card_id
        if cid in success_ids:
            tier1.append(card)
        else:
            rel = _score_relevance(card, keywords)
            if rel >= 0.6:
                tier2.append(card)
            else:
                tier3.append(card)
    # Helper to sort by newest first
    def _newest_first(c):
        try:
            dt = datetime.fromisoformat(c.stored_at)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            return datetime.min.replace(tzinfo=timezone.utc)
    tier1.sort(key=_newest_first, reverse=True)
    tier2.sort(key=_newest_first, reverse=True)
    tier3.sort(key=_newest_first, reverse=True)
    return tier1 + tier2 + tier3

# ---------------------------------------------------------------------------
# Context block builder
# ---------------------------------------------------------------------------
def _build_context_block(cards: List[Dict[str, Any]], new_card_ids: Set[str]) -> str:
    """Render the selected cards into a markdown block.

    The block contains a "NEW since your last run:" subsection for cards whose `seen_since_run`
    equals the current `run_id` (i.e. those in `new_card_ids`).
    """
    if not cards:
        return ""
    lines = ["--- RELEVANT PAST LEARNINGS ---"]
    # Separate new cards for a dedicated subsection
    new_cards = [c for c in cards if c.card_id in new_card_ids]
    if new_cards:
        lines.append("\nNEW since your last run:\n")
        for c in new_cards:
            content = c.content.strip()
            if content:
                lines.append(content)
                lines.append("---")
    # All other cards
    for c in cards:
        if c.card_id in new_card_ids:
            continue  # already displayed in NEW section
        content = c.content.strip()
        if content:
            lines.append(content)
            lines.append("---")
    lines.append("--- END RELEVANT PAST LEARNINGS ---")
    # Remove trailing separator if present
    if lines[-2] == "---":
        lines.pop(-2)
    return "\n".join(lines)

# ---------------------------------------------------------------------------
# Public API – enrichment
# ---------------------------------------------------------------------------
def enrich_prompt(run_id: str, packet: Dict[str, Any]) -> Dict[str, Any]:
    """Enrich a work‑packet prompt with a freshness‑aware, critically‑ordered context block.

    This function is a thin wrapper around the original `context_injector.enrich_prompt_with_context`
    but adds the extra steps required by the goal contract.
    """
    # Defensive type checks – required by the contract
    if not isinstance(run_id, str):
        raise TypeError("run_id must be a string")
    if not isinstance(packet, dict):
        raise TypeError("packet must be a dict")

    try:
        # 1. Load all durable cards (re‑use smart_memory loader)
        memory_root = Path(__file__).resolve().parents[2] / "memory" / "durable"
        all_cards = smart_memory._load_cards(memory_root)

        # 2. Load freshness state – which cards have been seen before?
        state = _load_context_state()
        seen_ids = set()
        for past_run, ids in state.items():
            if past_run != run_id:
                seen_ids.update(ids)

        # 3. Filter out previously‑seen cards and mark new ones
        fresh_cards = _filter_fresh_cards(all_cards, seen_ids, run_id)
        new_card_ids = {c.card_id for c in fresh_cards}

        # 4. Determine criticality ordering
        #    a) Load historic success cards (TIER1)
        success_ids = _load_success_card_ids()
        #    b) Extract keywords from the goal contract (reuse context_injector helper)
        contract = context_injector._load_goal_contract(run_id)
        keywords = context_injector._extract_keywords(contract)
        ordered_cards = _tier_cards(fresh_cards, success_ids, keywords)

        # 5. Build the markdown block
        context_block = _build_context_block(ordered_cards, new_card_ids)

        # 6. Insert the block into the packet (mirroring original injector behaviour)
        if context_block:
            original_prompt = packet.get("prompt", "")
            packet["prompt"] = context_block + "\n\n" + original_prompt
            # 7. Persist the updated state (record which cards were injected this run)
            state.setdefault(run_id, []).extend(list(new_card_ids))
            _save_context_state(state)
        else:
            LOGGER.info("No context block generated – returning original packet")

        return packet
    except Exception as exc:
        LOGGER.error("Context enrichment failed: %s", exc)
        # Return the original packet unchanged – downstream components can still run
        return packet

# ---------------------------------------------------------------------------
# Public API – usage tracking
# ---------------------------------------------------------------------------
def track_usage(run_id: str, agent_output_text: str) -> None:
    """Analyse `agent_output_text` for card references and update usage metadata.

    The function updates each durable card file (`usage_count` and `last_used`) and writes a per‑run
    `usage_report.json` containing a summary of all cards referenced in this run.
    """
    if not isinstance(run_id, str):
        raise TypeError("run_id must be a string")
    if not isinstance(agent_output_text, str):
        raise TypeError("agent_output_text must be a string")

    try:
        # Load all cards once – cheap compared to per‑card I/O
        memory_root = Path(__file__).resolve().parents[2] / "memory" / "durable"
        all_cards = smart_memory._load_cards(memory_root)
        card_by_id = {c.card_id: c for c in all_cards}

        # 1. Regex for explicit CARD_ID mentions
        explicit_ids = set(re.findall(r"CARD_[A-Z0-9]+", agent_output_text))

        # 2. Quoted snippet detection – look for any exact content surrounded by quotes
        quoted_snippets = re.findall(r"['\"]([^\"']{10,})['\"]", agent_output_text)
        snippet_matches: Set[str] = set()
        for snippet in quoted_snippets:
            for cid, card in card_by_id.items():
                if snippet.strip() == card.content.strip():
                    snippet_matches.add(cid)

        # Union of both detection methods
        referenced_ids = explicit_ids.union(snippet_matches)

        used_cards: List[str] = []
        now_iso = datetime.now(timezone.utc).isoformat()
        for cid in referenced_ids:
            card = card_by_id.get(cid)
            if not card:
                continue
            # Update usage fields – durable cards are stored as JSON files
            card_path = memory_root / f"{cid}.json"
            try:
                raw = json.loads(card_path.read_text(encoding="utf-8"))
                raw["usage_count"] = raw.get("usage_count", 0) + 1
                raw["last_used"] = now_iso
                card_path.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
                used_cards.append(cid)
            except Exception as exc:
                LOGGER.warning("Failed to update usage for %s: %s", cid, exc)

        # Write a per‑run usage report
        report = {
            "run_id": run_id,
            "timestamp": now_iso,
            "referenced_card_ids": list(referenced_ids),
            "updated_card_ids": used_cards,
            "summary": f"{len(used_cards)} cards usage‑tracked"
        }
        report_path = USAGE_REPORT_DIR / f"usage_report_{run_id}.json"
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        LOGGER.info("Usage report written to %s", report_path)
    except Exception as exc:
        raise UsageTrackingError(f"Failed during usage tracking: {exc}") from exc

# ---------------------------------------------------------------------------
# When executed as a script – simple sanity check
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Context engineer demo")
    parser.add_argument("run_id", help="Run identifier")
    parser.add_argument("packet", help="Path to JSON packet file")
    parser.add_argument("--track", action="store_true", help="Run usage tracking on a text file")
    parser.add_argument("--output", help="Where to write the enriched packet")
    args = parser.parse_args()
    if args.track:
        with open(args.packet, "r", encoding="utf-8") as f:
            text = f.read()
        track_usage(args.run_id, text)
    else:
        pkt = json.loads(Path(args.packet).read_text(encoding="utf-8"))
        enriched = enrich_prompt(args.run_id, pkt)
        out_path = Path(args.output) if args.output else Path("enriched_packet.json")
        out_path.write_text(json.dumps(enriched, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Enriched packet written to {out_path}")
