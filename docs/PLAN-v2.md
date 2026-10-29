# Title Agent v2: private, fast, on title.totalchb.com

Owner's goals (2026-10-29): **privacy, speed, our own domain.** Built the way the Universal Team Hub is built
(Vercel page + Firebase sign-in + Firestore), keeping everything the Title Agent already does.

## Decisions (owner, 2026-10-29)
| Question | Decision |
| --- | --- |
| Firebase project | **Separate** from the Universal Team Hub |
| Data | **Move to Firestore** (records) + Firebase Storage (PDFs, each review's full analysis); one-time copy, nothing lost |
| Who can sign in | **@totalchb.com only** (Google accounts, verified) |
| Address | **title.totalchb.com** |
| Design | **The Universal Team Hub's design**, not the Streamlit app's (owner, 2026-10-30): same views and formats across the team's apps. The new page reuses the hub's stylesheet (TCHB tokens, Baloo 2 / Nunito Sans) and its components: header, cards, pills, buttons, menus, light / dark |

## Architecture
```
Browser ── title.totalchb.com (Vercel: the page) ── Firebase Auth (Google, @totalchb.com)
   │                                                     │
   └── live reads/writes ── Firestore + Storage (security rules) ──┐
   └── "Read documents" / "Run review" / exports ── Engine (Cloud Run, Python: titleagent/) ── Claude
GitHub: code; pushes deploy the page (Vercel) and the engine (Cloud Run); Actions sends the 8 AM email (Resend).
```
- The AI key lives only in the engine. The engine accepts only Firebase ID tokens of verified @totalchb.com users.
- Reviews take 1–3 minutes: the engine writes progress and results into Firestore; the page watches them live.
- Data layout: see the docstring of `titleagent/firestore_store.py`.

## Phases
1. **Firestore data layer + copy** *(built 2026-10-29)*: `titleagent/firestore_store.py` has the same methods as
   `storage.Store`; the same tests run on both (Firestore through the local emulator,
   `scripts/firestore_emulator.sh`). `scripts/copy_to_firestore.py` copies everything with the same ids and checks
   the counts; it runs from GitHub (Actions → **Copy to Firestore**) with the repository's secrets, and is re-run on
   switch-over day so anything added meanwhile comes over. Until then the Streamlit app stays on Postgres
   (setting `FIREBASE_PROJECT_ID` in its secrets would switch it and the daily email to Firestore, if ever needed).
2. **Engine service** on Cloud Run *(built 2026-10-30)*: `engine/main.py` (FastAPI) around `titleagent/flows.py`
   (the screens' flows without a screen). Firebase ID-token check (verified @totalchb.com; admins from Settings);
   read → confirm → review, re-run, training, exports (incl. Closing Blockers only), Google export, list edits,
   report missing, item feedback, lessons, settings. Long steps write their current step to `jobs/{id}`; uploads
   come through Storage `uploads/<uid>/`. Tested end to end against the Firestore and Auth emulators, also as the
   built container. `Dockerfile` (engine only, `engine/requirements.txt`); `.github/workflows/deploy-engine.yml`
   builds and deploys on every engine change, signing in to Google without a key (`scripts/gcp_setup.sh`), then
   smoke-checks it. **Live since 2026-10-29**: https://title-agent-engine-622792668017.us-east1.run.app (Cloud Run,
   us-east1, project title-commitment-agent; repository RemyTCHB/TITLE-COMMITMENT-AGENT). A signed-in call against
   the real Firestore is first exercised by the new page (phase 3).
3. **New page** on Vercel built from the Universal Team Hub's design (its stylesheet and components, so the
   apps look and work alike): Analyze, Deal, Deals, Training, Knowledge, Settings; Firebase Google sign-in;
   Firestore and Storage security rules.
4. **Connections**: daily email from Firestore (done in phase 1), Google export script (unchanged), optional
   "Send blockers to the Team Hub" (separate projects: the engine writes with the hub's own service account).
5. **Switch-over**: a week side by side, `APP_URL` → https://title.totalchb.com, guide refresh, then retire the
   Streamlit app and the Postgres database (after a backup).

## Owner setup (one time, walked through step by step)
1. console.firebase.google.com, signed in as the owner's @totalchb.com account → **Add project** "TCHB Title Agent"
   (Analytics off).
2. **Upgrade to Blaze** (pay as you go; needed for Storage and Cloud Run; expected cost a few dollars a month).
   Set a budget alert.
3. **Firestore Database → Create** (production mode, location `nam5` or `us-east1`); **Storage → Get started**
   (same location).
4. **Authentication → Sign-in method → Google** (for phase 3).
5. **Project settings → Service accounts → Generate new private key**, pasted into GitHub (Settings → Secrets →
   Actions) as `FIREBASE_SERVICE_ACCOUNT_JSON`, with `FIREBASE_PROJECT_ID`. Used by the copy and the daily email.
   If Google blocks key creation, a Workspace admin turns off the organization policy *Disable service account key
   creation* for this project.
6. **Engine (phase 2)**: in Cloud Shell, run `scripts/gcp_setup.sh` (pasted); save the value it prints in GitHub as
   `GCP_WORKLOAD_IDENTITY_PROVIDER`, and add `ANTHROPIC_API_KEY` (and `GOOGLE_EXPORT_URL` / `GOOGLE_EXPORT_KEY`)
   as GitHub secrets. Then Actions → Deploy engine → Run workflow.
7. **Page (phase 3)**: Vercel project "title-commitment-agent" (root directory `web`) at
   https://title-commitment-agent.vercel.app and **https://title.totalchb.com**; Firestore and Storage rules
   published from `firebase/`; Authentication → Settings → Authorized domains lists both addresses.

## Costs
Cloud Run about $0–5/month at 30–100 reviews (it sleeps between them); Firestore and Storage most likely within the
free tier; Vercel Pro about $20 per member per month for company use; Anthropic and Resend unchanged.
