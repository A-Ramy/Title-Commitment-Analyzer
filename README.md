# Title Commitment Agent — Total Cash Home Buyers

**https://title.totalchb.com** · sign in with your @totalchb.com Google account.

Upload a title commitment (and the purchase contract) and the Title Commitment Agent lists **everything that has to happen
before the deal can close**: Closing Blockers, Before Closing items and Review / FYI, each traced to the page and
wording it comes from. TCs work the list in the app and export it (PDF, Word, Excel, CSV, Google Sheets / Docs,
everything or Closing Blockers only). The team trains it with worked commitments and **Report Missing Item**; admins
approve every lesson. A summary email goes out weekdays at 8:00 AM Eastern.

The user guide for the team: [`docs/guide/Title_Commitment_Agent_User_Guide.pdf`](docs/guide/Title_Commitment_Agent_User_Guide.pdf)
(rebuilt with `uv run python docs/guide/build_guide.py`).

Plans and decisions: [`docs/PLAN.md`](docs/PLAN.md) (the team's rules) and [`docs/PLAN-v2.md`](docs/PLAN-v2.md) (how
it runs today). Project rules: [`CLAUDE.md`](CLAUDE.md).

## How it runs

| Piece | Where | Folder |
| --- | --- | --- |
| The page (Universal Team Hub design) | Vercel, title.totalchb.com | `web/` |
| The engine: reads commitments, runs reviews, builds exports, holds the AI key | Google Cloud Run | `engine/`, `titleagent/` |
| Data: deals, lists, PDFs, lessons, settings | Firebase (Firestore + Storage), project `title-commitment-agent` | rules in `firebase/` |
| Sign-in | Firebase Authentication (Google, @totalchb.com only) | |
| The 8 AM email (Closing Blockers only) | Google Cloud Scheduler → the engine → Resend, from title-agent@totalchb.com; GitHub Actions later as a backup | `titleagent/daily.py`, `scripts/scheduler_setup.sh` |
| Google Sheets / Docs exports | A Google Apps Script in the team's Drive | `titleagent/exports/google_export.gs` |
| Closing Blockers → Universal Team Hub (both ways) | Engine after each change + a catch-up with the morning email run → hub.totalchb.com/api/title-agent | `titleagent/hub.py`, `scripts/hub_sync.py` |

Every push deploys itself: Vercel rebuilds the page; `.github/workflows/deploy-engine.yml` rebuilds the engine, deploys
it to Cloud Run (keyless sign-in to Google, `scripts/gcp_setup.sh`) and smoke-checks it.

## How a review works

1. **Read** – Claude (Opus 5.5) reads the commitment PDF itself, scanned pages included, and reports Schedule A and
   every numbered Schedule B-I requirement and B-II exception.
2. **Numbering check (code, not AI)** – the engine reads the PDF text on its own and confirms every printed item
   number was picked up. Gaps go back to the AI once; anything still missing shows in red.
3. **Confirm** – the uploader confirms the deal details the agent read (address, deal type, closing date, TC).
4. **Action list** – every B-I / B-II number gets a disposition (code checks none is skipped), plus the professional
   checklist (`titleagent/checklist.py`, 34 checks) and every approved lesson.
5. **Second review** – an independent pass that only asks "what would stop this closing that isn't on the list?"
6. **Proof** – every quote is checked against the page it cites (✓ / ✗; scanned pages can't be checked).

## Working on it

Requires [uv](https://docs.astral.sh/uv/), Node 20+ and Java 11+ (for the Firebase emulators).

```bash
uv sync && (cd web && npm install)
npx firebase-tools@13.29.1 emulators:start --project title-commitment-agent     # Auth, Firestore, Storage
FIREBASE_PROJECT_ID=title-commitment-agent FIRESTORE_EMULATOR_HOST=127.0.0.1:8085 \
  STORAGE_EMULATOR_HOST=http://127.0.0.1:9199 FIREBASE_AUTH_EMULATOR_HOST=127.0.0.1:9099 \
  ALLOWED_ORIGINS=http://127.0.0.1:5173 TITLE_AGENT_DEMO=1 uv run uvicorn engine.main:app --port 8090
cd web && VITE_EMULATORS=1 VITE_ENGINE_URL=http://127.0.0.1:8090 npx vite        # http://127.0.0.1:5173
```

`TITLE_AGENT_DEMO=1` uses scripted answers on a made-up sample commitment (no AI cost); in the browser console,
`__emulatorSignIn('you@totalchb.com')` signs in on the emulator.

Checks: `uv run ruff check .` and `uv run pytest` (storage and engine tests need the Firestore emulator:
`scripts/firestore_emulator.sh &` then `FIRESTORE_EMULATOR_HOST=127.0.0.1:8085 uv run pytest`); `cd web && npm run build`.

Measure accuracy on real worked commitments (kept **outside** the repo; see the script's docstring for the
`gold.json` format): `uv run python scripts/evaluate.py /path/to/examples`

## Privacy

Commitments and contracts contain names, addresses and loan numbers. They live only in the Firebase project, readable
by signed-in @totalchb.com accounts (the security rules) and changed only through the engine. They are never committed
to git: `*.pdf`, exports and `.data/` are gitignored, and tests use made-up data (`titleagent/demo.py`).
