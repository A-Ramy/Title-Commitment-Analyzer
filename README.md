# Title Agent — Total Cash Home Buyers

Upload a title commitment (and the purchase contract) and the Title Agent lists **everything that has to happen
before the deal can close**: Closing Blockers, Before Closing items and Review / FYI, each traced to the page and
wording it comes from. TCs work the list in the app and export it to Google Sheets, Google Docs, Word, PDF, Excel or
CSV. The team trains it with worked commitments and **Report Missing Item**; admins approve every lesson.

Plan and decisions: [`docs/PLAN.md`](docs/PLAN.md). Project rules: [`CLAUDE.md`](CLAUDE.md).

## How a review works

1. **Read** – Claude (Opus 5.5) reads the commitment PDF itself, scanned pages included, and reports Schedule A and
   every numbered Schedule B-I requirement and B-II exception.
2. **Numbering check (code, not AI)** – the app reads the PDF text on its own and confirms every printed item number
   was picked up. Gaps go back to the AI once; anything still missing shows in red on the coverage panel.
3. **Confirm** – the uploader confirms the deal details the agent read (address, deal type, closing date, TC).
4. **Action list** – every B-I / B-II number gets a disposition (code checks none is skipped), plus the professional
   checklist (`titleagent/checklist.py`, 34 checks incl. double close, novation, subject-to, seller financing) and
   every approved lesson.
5. **Second review** – an independent pass that only asks "what would stop this closing that isn't on the list?"
6. **Proof** – every quote is checked against the page it cites (✓ / ✗; scanned pages can't be checked).

Due dates come from the closing date (Settings). Updated commitments go on the same deal: statuses and notes carry
over, and the list shows what's new and what the title company removed.

## Run it locally

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync
cp .env.example .env              # add ANTHROPIC_API_KEY
uv run streamlit run app.py       # http://localhost:8501
```

Without a key, look at the UI with a made-up sample deal: `TITLE_AGENT_DEMO=1 uv run streamlit run app.py`
(tick "Use the made-up sample commitment" on Analyze). For local work against real data without a sign-in, add
`TITLE_AGENT_NO_LOGIN=1` to `.env`; never set it in the cloud.

Tests and lint: `uv run pytest` · `uv run ruff check .`

Measure accuracy on real worked commitments (kept **outside** the repo; see the script's docstring for the
`gold.json` format): `uv run python scripts/evaluate.py /path/to/examples`

## Sign-in (the app is public, so it locks itself)

Streamlit Community Cloud allows one private app per account and the Projection Tool uses it, so this app's URL is
public. The app is **locked** until one of these is set in its secrets (template: `.streamlit/secrets.toml.example`):

- **Team password (stopgap, 1 minute):** `APP_PASSWORD`. People enter their work email and the password once; the
  browser stays signed in for 30 days (reloads and links from the daily email open straight in) until they click
  Sign Out. Changing `APP_PASSWORD` signs everyone out. The email is not verified, so anyone with the password could
  claim to be an admin.
- **Google sign-in (recommended, ~15 minutes):** Google Cloud console → APIs & Services → Credentials → Create
  OAuth client ID (Web application) → authorized redirect URI `https://YOUR-APP.streamlit.app/oauth2callback`.
  Put the client ID and secret in the `[auth]` section with a random `cookie_secret`. Only verified Google accounts
  at `ALLOWED_DOMAINS` (default `totalchb.com`) or listed in `ALLOWED_EMAILS` get in.

## Go live (Streamlit Community Cloud, like the Projection Tool)

1. **Database** – create a Postgres database (Neon or Supabase, free tier to start) and copy its connection string.
2. **App** – on share.streamlit.io: New app → this repository, branch, `app.py`. (It can't be private on the free
   plan while the Projection Tool is; the sign-in protects it.)
3. **Secrets** (App → Settings → Secrets):
   ```toml
   ANTHROPIC_API_KEY = "sk-ant-..."
   DATABASE_URL = "postgresql://..."
   APP_PASSWORD = "..."   # or the Google sign-in [auth] section (see Sign-in above)
   ```
4. **Settings page** – add the admins (Owner, CTO, TC, TC Assistant), the TCs and the email recipients.
5. **Training set** – on the Training tab, upload each worked commitment with the closer's list. The 10 lessons
   learned from the first 8 examples are already built in.

### Google Sheets / Docs exports (a Shared Drive on the totalchb.com Google Workspace)
The app writes as a **service account** (a robot Google user), which has no Drive storage of its own, so exports go
into a folder in a **Shared Drive**.
1. **Google Cloud** (console.cloud.google.com, signed in with a totalchb.com account): create a project (e.g.
   "Title Agent") → APIs & Services → Library → enable **Google Drive API** → IAM & Admin → Service Accounts → Create
   (name `title-agent`, no roles) → open it → Keys → Add key → JSON. If key creation is blocked, a Workspace admin
   turns off the organization policy *Disable service account key creation* for this project.
2. **Shared Drive**: open the drive → Manage members → add the service account's email
   (`title-agent@<project>.iam.gserviceaccount.com`) as **Content Manager**. If Drive refuses because it's outside
   totalchb.com, a Workspace admin allows it (Admin console → Apps → Google Workspace → Drive and Docs → Sharing
   settings, and the Shared Drive's own setting for people outside the organization).
3. **Secrets** (Streamlit → App → Settings → Secrets): paste the key file between triple quotes:
   ```toml
   GOOGLE_SERVICE_ACCOUNT_JSON = '''
   { ...the whole key file... }
   '''
   ```
4. **App → Settings → Google Exports**: paste the folder's link, Save, click **Test Google Folder**.

### Daily email (from @totalchb.com)
1. resend.com → add the domain `totalchb.com` → add the DNS records it shows (2–3 records, one time).
2. Create an API key. In this GitHub repository: Settings → Secrets → Actions: `DATABASE_URL`, `RESEND_API_KEY`;
   Variables: `APP_URL` (the app's link). The key stays in GitHub; Settings → Connections shows when the
   email last went out.
3. `.github/workflows/daily-email.yml` sends it every weekday at about 8:00 AM Eastern, all year (Run workflow to
   test it).

## Privacy

Commitments and contracts contain names, addresses and loan numbers. They are stored only in the app's private
database, kept indefinitely (owner's decision), and never committed to git: `*.pdf`, exports and `.data/` are
gitignored. Never put real deal data in tests, logs, issues or commit messages.
