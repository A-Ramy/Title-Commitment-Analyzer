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
   the counts. Setting `FIREBASE_PROJECT_ID` switches today's app and the daily email to Firestore, so the data can
   move before the new page is ready.
2. **Engine service** on Cloud Run: sign-in check, read documents, run review (progress in Firestore), exports,
   feedback and lessons. Dockerfile; deploy from GitHub.
3. **New page** on Vercel in the hub's style and the TCHB brand: Analyze, Deal, Deals, Training, Knowledge,
   Settings; Firebase Google sign-in; Firestore and Storage security rules.
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
5. **Project settings → Service accounts → Generate new private key** (for the copy, GitHub Actions and the
   interim Streamlit app). If Google blocks key creation, a Workspace admin turns off the organization policy
   *Disable service account key creation* for this project.
6. Domain: add `title.totalchb.com` in Vercel (phase 3) and one DNS record where totalchb.com's DNS is managed.

## Costs
Cloud Run about $0–5/month at 30–100 reviews (it sleeps between them); Firestore and Storage most likely within the
free tier; Vercel Pro about $20 per member per month for company use; Anthropic and Resend unchanged.
