# .agentic-pi/runtime/smart_memory.py
"""Smart memory pipeline: compression, scoring, deduplication, truncation, and quality tracking.
"""

import importlib.util
import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Tuple, Set

# Optional tokenisation – use simple split if nltk unavailable
def _tokenize(txt: str):
    try:
        import nltk
        return nltk.word_tokenize(txt.lower())
    except Exception:
        return txt.lower().split()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------
class SmartMemoryError(Exception):
    """Base class for all smart‑memory errors."""

class CardLoadError(SmartMemoryError):
    """Raised when a memory card cannot be read or parsed."""

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------
@dataclass
class Card:
    card_id: str
    content: str
    source: str = ""
    agent: str = ""
    outcome: str = "UNKNOWN"
    stored_at: str = ""
    weight: float = 1.0
    # optional metadata used for compression
    failure_pattern: str = ""
    goal_type: str = ""

    def age_seconds(self) -> float:
        """Return age in seconds from now. Invalid timestamps yield 0 (neutral)."""
        try:
            dt = datetime.fromisoformat(self.stored_at)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            return (now - dt).total_seconds()
        except Exception:
            return 0.0

@dataclass
class ScoredCard:
    card: Card
    score: float
    recency: float
    relevance: float
    success_rate: float

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _load_goal_contract(run_id: str) -> Dict[str, Any]:
    """Load the goal contract for the given run.

    Raises:
        CardLoadError: if the contract cannot be read or parsed.
    """
    contract_path = Path(__file__).resolve().parents[2] / ".agentic-runs" / run_id / "goal_contract.json"
    if not contract_path.is_file():
        raise CardLoadError(f"Goal contract not found at {contract_path}")
    try:
        return json.loads(contract_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise CardLoadError(f"Failed to parse goal contract: {exc}") from exc


def _extract_keywords(contract: Dict[str, Any]) -> List[str]:
    """Extract a set of lower‑cased keywords from the contract, filtering stop‑words.
    """
    stopwords = {
        "a", "an", "the", "and", "or", "but", "if", "else", "for", "while",
        "function", "functions", "to", "of", "in", "on", "as", "is", "are", "be", "by",
        "with", "from", "that", "this", "it", "its", "at", "not", "do", "does", "did",
        "has", "have", "had", "will", "shall", "should", "could", "would", "can", "may",
        "might", "must"
    }
    tokens: Set[str] = set()
    # raw_user_prompt
    raw = contract.get("raw_user_prompt", "")
    for token in raw.split():
        token = token.strip(".,!?:;\"'()[]{}<>-_\n\t")
        low = token.lower()
        if low and low not in stopwords:
            tokens.add(low)
    # final_outputs
    for out in contract.get("final_outputs", []):
        for token in str(out).split():
            token = token.strip(".,!?:;\"'()[]{}<>-_\n\t")
            low = token.lower()
            if low and low not in stopwords:
                tokens.add(low)
    # done_criteria
    for crit in contract.get("done_criteria", []):
        for token in str(crit).split():
            token = token.strip(".,!?:;\"'()[]{}<>-_\n\t")
            low = token.lower()
            if low and low not in stopwords:
                tokens.add(low)
    return list(tokens)


def _load_cards(root: Path) -> List[Card]:
    """Load gated durable MemPalace JSONL cards and normalise fields."""
    memory_root = root if root.name != "durable" else root.parent
    if not memory_root.is_dir():
        logging.warning("Memory root %s does not exist", memory_root)
        return []
    adapter_path = Path(__file__).resolve().parent / "mempalace_adapter.py"
    spec = importlib.util.spec_from_file_location("mempalace_adapter", adapter_path)
    adapter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(adapter)

    cards: List[Card] = []
    for raw in adapter.load_durable_cards(memory_root):
        if raw.get("authority_level") != "advisory_only" or raw.get("can_certify_done") is not False:
            continue
        if raw.get("card_status") in {"deprecated", "rejected"}:
            continue
        content = str(raw.get("content") or "")
        if not content.strip():
            continue
        cards.append(
            Card(
                card_id=raw.get("card_id", ""),
                content=content,
                source=raw.get("source_phase", ""),
                agent="memory_write_gate",
                outcome=raw.get("card_status", "UNKNOWN"),
                stored_at=raw.get("promoted_at") or raw.get("created_at", ""),
                weight=float(raw.get("helpful_count", 0) + 1),
                failure_pattern=";".join(raw.get("do_not_use_when", [])),
                goal_type=raw.get("type", ""),
            )
        )
    return cards


def _group_by_pattern(cards: List[Card]) -> Dict[Tuple[str, str], List[Card]]:
    """Group cards by (failure_pattern, goal_type). Empty strings are treated as a wildcard.
    """
    groups: Dict[Tuple[str, str], List[Card]] = defaultdict(list)
    for c in cards:
        key = (c.failure_pattern, c.goal_type)
        groups[key].append(c)
    return groups


def _merge_group(group: List[Card]) -> Card:
    """Merge a list of cards that share the same pattern/goal_type.

    The merged content is the concatenation of *unique* sentences (split on '.').
    Weight is summed. The newest ``stored_at`` is retained.
    """
    if not group:
        raise ValueError("Empty group cannot be merged")
    # Preserve newest timestamp
    newest = max(group, key=lambda c: c.age_seconds())
    # Token‑level deduplication of sentences
    seen: Set[str] = set()
    merged_sentences: List[str] = []
    for c in group:
        for sent in c.content.split('.'):
            sent = sent.strip()
            if not sent:
                continue
            if sent not in seen:
                seen.add(sent)
                merged_sentences.append(sent)
    merged_content = '. '.join(merged_sentences) + ('.' if merged_sentences else '')
    merged_weight = sum(c.weight for c in group)
    return Card(
        card_id=f"merged-{hash('_'.join([c.card_id for c in group])) & 0xffffffff:x}",
        content=merged_content,
        source=group[0].source,
        agent=group[0].agent,
        outcome=group[0].outcome,
        stored_at=newest.stored_at,
        weight=merged_weight,
        failure_pattern=group[0].failure_pattern,
        goal_type=group[0].goal_type
    )


def compress_cards(cards: List[Card]) -> List[Card]:
    """Compress cards by merging those with identical ``failure_pattern`` or ``goal_type``.

    Returns a new list of cards where each group is replaced by a single merged card.
    """
    groups = _group_by_pattern(cards)
    merged: List[Card] = []
    for key, group in groups.items():
        if len(group) > 1:
            merged.append(_merge_group(group))
        else:
            merged.append(group[0])
    return merged


def _relevance_score(card: Card, keywords: List[str]) -> float:
    """Compute relevance as the fraction of keywords appearing in the card content.
    """
    if not keywords:
        return 0.0
    content_tokens = set(_tokenize(card.content))
    matches = sum(1 for kw in keywords if kw in content_tokens)
    return matches / len(keywords)


def _success_rate(card: Card) -> float:
    """Map ``outcome`` to a numeric success rate.
    """
    success_map = {
        "DONE_PASS": 1.0,
        "CERTIFIED_DONE": 1.0,
        "DONE_FAIL": 0.5,
        "NOT_DONE": 0.0,
        "UNKNOWN": 0.5
    }
    return success_map.get(card.outcome.upper(), 0.0)

#@ Requires(lambda cards: isinstance(cards, list) and all(isinstance(c, Card) for c in cards), "cards must be a list of Card objects")
#@ Requires(lambda keywords: isinstance(keywords, list) and all(isinstance(k, str) for k in keywords), "keywords must be a list of strings")
#@ Ensures(lambda result: isinstance(result, list) and all(isinstance(sc, ScoredCard) for sc in result), "result must be a list of ScoredCard objects")

def score_cards(cards: List[Card], keywords: List[str]) -> List[ScoredCard]:
    """Assign a composite score to each card.

    The score is ``recency * relevance * success_rate`` where each component is normalised to [0, 1].
    """
    # Normalise recency – newest card gets 1, oldest gets 0
    ages = [c.age_seconds() for c in cards]
    max_age = max(ages) if ages else 1.0
    scored: List[ScoredCard] = []
    for c in cards:
        recency = 0.5 ** (c.age_seconds() / 604800.0)
        relevance = _relevance_score(c, keywords)
        success = _success_rate(c)
        score = recency * relevance * success
        scored.append(ScoredCard(card=c, score=score, recency=recency, relevance=relevance, success_rate=success))
    # Sort descending by score
    scored.sort(key=lambda sc: sc.score, reverse=True)
    return scored


def _jaccard_similarity(a: str, b: str) -> float:
    """Return Jaccard similarity of token sets of two strings.
    """
    set_a = set(_tokenize(a))
    set_b = set(_tokenize(b))
    if not set_a and not set_b:
        return 1.0
    intersection = set_a.intersection(set_b)
    union = set_a.union(set_b)
    return len(intersection) / len(union)


def dedup_cards(cards: List[Card]) -> List[Card]:
    """Deduplicate cards with >80% content overlap. Keep the newer card.
    """
    if not cards:
        return []
    # Sort by stored_at descending (newest first)
    sorted_cards = sorted(cards, key=lambda c: c.stored_at, reverse=True)
    kept: List[Card] = []
    for cand in sorted_cards:
        duplicate = False
        for kept_card in kept:
            if _jaccard_similarity(cand.content, kept_card.content) > 0.8:
                duplicate = True
                break
        if not duplicate:
            kept.append(cand)
    return kept


def truncate_cards(cards: List[Card], token_budget: int) -> List[Card]:
    """Greedy knapsack truncation to fit ``token_budget`` characters.

    Cards are taken in descending score order (caller must sort). If a card would exceed the budget,
    it is truncated from the end to exactly fill the remaining space.
    """
    selected: List[Card] = []
    used = 0
    for c in cards:
        remaining = token_budget - used
        if remaining <= 0:
            break
        content_len = len(c.content)
        if content_len <= remaining:
            selected.append(c)
            used += content_len
        else:
            # Truncate – keep the first ``remaining`` characters, add ellipsis
            truncated = c.content[:remaining] + "..."
            new_card = Card(
                card_id=c.card_id,
                content=truncated,
                source=c.source,
                agent=c.agent,
                outcome=c.outcome,
                stored_at=c.stored_at,
                weight=c.weight,
                failure_pattern=c.failure_pattern,
                goal_type=c.goal_type
            )
            selected.append(new_card)
            used = token_budget
            break
    return selected


def build_context_block(run_id: str, token_budget: int = 2000) -> str:
    """High‑level helper used by ``context_injector``.

    Steps:
    1. Load goal contract → extract keywords.
    2. Load all durable cards.
    3. Compress → dedup → score → truncate.
    4. Return a formatted advisory-memory block.

    If any step fails, an empty string is returned and the error is logged.
    """
    try:
        contract = _load_goal_contract(run_id)
        keywords = _extract_keywords(contract)
        root = Path(__file__).resolve().parents[2] / ".agentic-pi" / "memory"
        cards = _load_cards(root)
        if not cards:
            logging.info("No memory cards found for %s", run_id)
            return ""
        # 1) Compression
        cards = compress_cards(cards)
        # 2) Deduplication
        cards = dedup_cards(cards)
        # 3) Scoring
        scored = score_cards(cards, keywords)
        # 4) Truncate – we need the raw Card objects again, so extract them in order
        ordered_cards = [sc.card for sc in scored]
        selected = truncate_cards(ordered_cards, token_budget)
        # 5) Format
        if not selected:
            return ""
        lines = ["--- RELEVANT ADVISORY MEMORY (NOT CERTIFICATION) ---"]
        for i, c in enumerate(selected):
            content = c.content.strip()
            if not content:
                continue
            if i > 0:
                lines.append("---")
            lines.append(content)
        lines.append("--- END RELEVANT ADVISORY MEMORY ---")
        return "\n".join(lines)
    except SmartMemoryError as exc:
        logging.error("Smart memory error: %s", exc)
        return ""
    except Exception as exc:
        logging.exception("Unexpected error in build_context_block")
        return ""


def record_injection_quality(run_id: str, success: bool, used_card_ids: List[str]) -> None:
    """Persist a JSON quality report for the given run.

    The file is written to ``/.agentic-pi/runtime/injection_quality.json``.
    """
    report = {
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "success": success,
        "used_card_ids": used_card_ids,
        "summary": "success" if success else "failure",
    }
    out_path = Path(__file__).resolve().parent / "injection_quality.json"
    try:
        out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        logging.info("Wrote injection quality report to %s", out_path)
    except Exception as exc:
        logging.error("Failed to write injection quality report: %s", exc)

# ---------------------------------------------------------------------------
# CLI entry point (optional, for manual testing)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Smart memory context builder")
    parser.add_argument("run_id", help="Run identifier (e.g. smartmem)")
    parser.add_argument("--budget", type=int, default=2000, help="Token budget in characters")
    args = parser.parse_args()
    ctx = build_context_block(args.run_id, args.budget)
    print(ctx)
