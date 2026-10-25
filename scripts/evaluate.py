"""Score the agent against closers' lists: runs the full review on each worked commitment and reports how many of
the closer's items the agent found, plus what it missed and the Closing Blockers it added.

The examples hold real deal data, so they live OUTSIDE the repo. Point the script at a folder with the PDFs and a
gold.json:

    [{"file": "Commitment_Package_1.pdf", "deal_type": "Wholesale (Assignment)",
      "expert": ["3. Secure and record a Satisfaction of ..."]}, ...]

    ANTHROPIC_API_KEY=... uv run python scripts/evaluate.py /path/to/examples
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from titleagent import pipeline, prompts, training  # noqa: E402
from titleagent.config import load_secrets  # noqa: E402
from titleagent.llm import ClaudeLLM, Usage  # noqa: E402


def main(folder: str) -> int:
    secrets = load_secrets()
    if not secrets.has_ai:
        print("Set ANTHROPIC_API_KEY first.", file=sys.stderr)
        return 1
    root = Path(folder)
    cases = json.loads((root / "gold.json").read_text())
    llm = ClaudeLLM(secrets.anthropic_api_key)
    lessons = list(prompts.SEED_LESSONS)
    found = total = 0
    spend = 0.0
    for case in cases:
        usage = Usage()
        docs = pipeline.Documents((root / case["file"]).read_bytes())
        structure, gaps = pipeline.read_documents(llm, docs, lessons, usage)
        analysis = pipeline.review(llm, docs, structure, pipeline.DealInfo(deal_type=case.get("deal_type", "")),
                                   lessons, usage, gaps)
        blockers = [i for i in analysis.items if i.priority == "blocker"]
        expert = case["expert"]
        if expert:
            result = training.compare(llm, docs, prompts.system_prompt(lessons), expert, analysis.items, usage)
        else:
            result = training.Comparison(matched=[], missed=[], extra=blockers)
        found += len(result.matched)
        total += len(result.matched) + len(result.missed)
        spend += usage.cost
        cov = analysis.coverage
        print(f"\n== {case['file']} · {len(analysis.items)} items, {len(blockers)} blockers · coverage "
              f"{cov.percent}% · ${usage.cost:.2f}")
        print(f"   closer items found: {len(result.matched)}/{len(result.matched) + len(result.missed)}")
        for e, lesson in result.missed:
            print(f"   MISSED: {e[:110]}\n           lesson: {lesson}")
        for b in blockers:
            if all(b is not m for _, m in result.matched):
                print(f"   extra blocker: {b.title}")
        if not cov.complete:
            print(f"   COVERAGE GAPS: {cov.numbering_gaps + cov.unaddressed}")
    print(f"\nTotal: found {found}/{total} closer items ({found / total:.0%}) · AI cost ${spend:.2f}" if total else
          f"\nAI cost ${spend:.2f}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))
