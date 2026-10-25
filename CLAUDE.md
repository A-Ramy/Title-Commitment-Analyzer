# CLAUDE.md — Title Agent (Total Cash Home Buyers)

Streamlit app that reviews title commitments and lists everything needed to close. `docs/PLAN.md` holds the owner's
decisions (section 0); keep this file in sync when a rule changes.

## Non-negotiables
- **Never leave a numbered item behind.** Every Schedule B-I and B-II number must get a disposition; the numbering
  check (`titleagent/numbering.py`) is code, not AI, and its gaps are shown, never hidden. Don't weaken it.
- **Privacy.** Commitments, contracts, exports and the closers' lists are real deal data: never commit them, never
  copy them into tests, fixtures, prompts, lessons, logs or commit messages. Tests use `titleagent/demo.py`
  (made-up data). `*.pdf`, `.data/` and exports are gitignored.
- **Lessons are general rules** (no names, amounts, case numbers) and go live only after an admin approves them.
- Secrets only from env / Streamlit secrets (`titleagent/config.py`). Never in code or chat.

## The team's standard (from the 8 worked commitments, owner 2026-10-25)
- **Closing Blocker** = needs money paid to, or a document from, someone outside the closing table, or a court /
  government action: mortgages (incl. lis pendens), judgments (current or prior owner), tax-lien certificates,
  state / city tax liens, workers' comp liens, municipal maintenance liens, delinquent utilities, taxes sold to a
  third party, quiet title judgment entries, recorded memoranda (agreement / lease / option / wind) to terminate,
  commitment errors.
- **Before Closing** = routine requirements handled in the normal course (deed, premium, entity docs, FinCEN,
  HOA statement, affidavits, transfer forms, bring-down, taxes due shown in B-II).
- **Review / FYI** = standard exceptions and notes. A clean title has zero blockers.
- The TC owns every item; `provided_by` is who actually has it.

## Code map
- `titleagent/` (no Streamlit): `pipeline.py` (steps), `prompts.py` (system prompt, seed lessons), `checklist.py`,
  `numbering.py`, `grounding.py`, `compare.py` (updated commitments), `llm.py` (Claude calls: structured output,
  streaming, server-side fallback), `storage.py`, `exports/`, `emailer.py`, `training.py`, `demo.py`.
- `ui/` (brand shared with the Projection Tool: same `brand.css` / tokens; Streamlit pinned to the same version),
  `views/` one file per page, `app.py` navigation.
- Model: `claude-opus-5-5`, effort `high` (accuracy first). The system prompt must stay identical across a run's
  calls (prompt caching): put per-deal details in the step's task, not the system prompt.

## Checks before pushing
`uv run ruff check .` and `uv run pytest`. UI changes: run `TITLE_AGENT_DEMO=1 uv run streamlit run app.py` and look.
