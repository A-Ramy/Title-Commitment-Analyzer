"""Training: compare the agent's list with a closer's list for the same commitment. Every item the agent missed
becomes a suggested lesson (a general rule, no names), which an admin approves before it goes live."""

from __future__ import annotations

import json
from dataclasses import dataclass

from titleagent import prompts
from titleagent.llm import LLM, Usage
from titleagent.models import ActionItem, CompareOut
from titleagent.pipeline import Documents


@dataclass
class Comparison:
    matched: list[tuple[str, ActionItem]]  # (closer's item, agent item)
    missed: list[tuple[str, str]]  # (closer's item, suggested lesson)
    extra: list[ActionItem]  # agent items the closer did not list

    @property
    def recall(self) -> float:
        total = len(self.matched) + len(self.missed)
        return 1.0 if total == 0 else len(self.matched) / total


def parse_expert_list(text: str) -> list[str]:
    """One item per numbered paragraph or line ("7. Payment and release of ..."), blank lines ignored."""
    import re

    chunks = re.split(r"\n\s*(?=\(?\d{1,3}[.)]\s)|\n\s*\n", text.strip())
    out = [re.sub(r"\s+", " ", c).strip() for c in chunks]
    return [c for c in out if len(c) > 3]


def compare(llm: LLM, documents: Documents, system: str, expert: list[str], agent: list[ActionItem],
            usage: Usage) -> Comparison:
    agent_view = {i: {"title": a.title, "action": a.action, "sources": [s.ref for s in a.sources]}
                  for i, a in enumerate(agent)}
    task = prompts.COMPARE_TASK.format(expert=json.dumps(dict(enumerate(expert)), indent=1),
                                       agent=json.dumps(agent_view, indent=1))
    out = llm.ask(step="compare", system=system, docs=documents.docs(), task=task, schema=CompareOut, usage=usage)
    matched, missed, used = [], [], set()
    for m in out.matches:
        if not 0 <= m.expert_index < len(expert):
            continue
        if m.agent_index is not None and 0 <= m.agent_index < len(agent):
            matched.append((expert[m.expert_index], agent[m.agent_index]))
            used.add(m.agent_index)
        else:
            missed.append((expert[m.expert_index], m.lesson))
    seen = {m.expert_index for m in out.matches}
    missed += [(e, "") for i, e in enumerate(expert) if i not in seen]  # anything the comparison skipped
    extra = [agent[i] for i in out.extra_agent_indexes if 0 <= i < len(agent) and i not in used]
    return Comparison(matched=matched, missed=missed, extra=extra)
