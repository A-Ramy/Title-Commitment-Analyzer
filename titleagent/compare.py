"""Updated commitments and re-runs: match the new list to the deal's previous list so statuses, notes and keys
carry over, and mark what is new and what the title company removed (cleared).

Item numbers shift between commitment revisions, so matching uses what the item is about (its headline and quoted
wording), not its number."""

from __future__ import annotations

import hashlib
import re
from difflib import SequenceMatcher

from titleagent.grounding import norm
from titleagent.models import ActionItem

MATCH_AT = 0.62


def _signature(item: ActionItem) -> str:
    quote = next((s.quote for s in item.sources if s.quote), "")
    return norm(f"{item.title} {quote[:160]}")


def make_key(item: ActionItem) -> str:
    ref = next((s.ref for s in item.sources if s.ref), item.category)
    slug = re.sub(r"[^a-z0-9]+", "-", ref.lower()).strip("-")[:24] or "item"
    return f"{slug}-{hashlib.sha1(norm(item.title).encode()).hexdigest()[:6]}"


def similarity(a: ActionItem, b: ActionItem) -> float:
    return SequenceMatcher(None, _signature(a), _signature(b)).ratio()


def carry_over(new: list[ActionItem], previous: list[ActionItem], mark_changes: bool) -> list[ActionItem]:
    """New items take the key, status and notes of their best previous match. With mark_changes (an updated
    commitment), unmatched new items are "new" and unmatched open previous items come back as "removed"."""
    prev = [p for p in previous if p.change != "removed"]
    pairs = sorted(((similarity(n, p), i, j) for i, n in enumerate(new) for j, p in enumerate(prev)), reverse=True)
    taken_new: dict[int, int] = {}
    taken_prev: set[int] = set()
    for score, i, j in pairs:
        if score < MATCH_AT:
            break
        if i in taken_new or j in taken_prev:
            continue
        taken_new[i] = j
        taken_prev.add(j)

    out: list[ActionItem] = []
    used_keys: set[str] = set()
    for i, n in enumerate(new):
        if i in taken_new:
            p = prev[taken_new[i]]
            item = n.model_copy(update={"key": p.key, "status": p.status, "notes": p.notes, "change": ""})
        else:
            item = n.model_copy(update={"key": n.key or make_key(n), "change": "new" if mark_changes else ""})
        while item.key in used_keys:
            item = item.model_copy(update={"key": item.key + "x"})
        used_keys.add(item.key)
        out.append(item)

    for j, p in enumerate(prev):
        if j in taken_prev:
            continue
        if p.origin == "feedback":  # an item a person added stays until they clear it
            out.append(p)
        elif mark_changes:
            out.append(p.model_copy(update={"change": "removed"}))
    return out
