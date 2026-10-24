# Title Commitment Analyzer: Plan (draft for review)

An app that reads an uploaded **title commitment** the way a professional title agent would and returns
**every item that must be handled for the deal to close**, as a checklist the team can export to Google Sheets,
CSV, PDF, Word or Google Docs. It learns from the team: upload a commitment, type the list a pro would have
made, and the agent compares, learns the gap, and does better next time. A **Report Missing Item** button
feeds the same learning loop from live deals.

Brand: Total Cash Home Buyers, same as the Projection Tool (Baloo 2 + Nunito Sans, Victoria indigo
`#4D458A`, Cardinal red `#BD2239`, Salem green `#109648`, frosted glass, Light / Dark switch). The draft
screen is in [`docs/draft/index.html`](draft/index.html).

---

## 1. Recommendation: Streamlit (same stack as the Projection Tool)

| | **Streamlit** (recommended) | **Vercel** (Next.js) |
|---|---|---|
| Theme | Reuse `ui/brand.css` + `ui/brand.py` from Projection as-is. Identical look on day one. | Port the same CSS tokens to React. Looks the same, but it's a second copy to keep in sync. |
| Long analyses | A 40-page commitment can take 1–3 minutes to analyze. Streamlit has no request timeout. | Serverless functions have time limits by plan; needs a background job/queue for long runs. |
| Big PDFs | Upload limit is configurable (default 200 MB). | Request bodies are capped at a few MB; uploads must go direct to blob storage first. |
| PDF / export tooling | Python: PyMuPDF / pdfplumber (text + page numbers), python-docx (Word), WeasyPrint (PDF), gspread + Google Docs API. | JS equivalents exist but are thinner for PDF parsing and Word output. |
| Build time to v1 | ~3–4 weeks | ~5–7 weeks |
| Where it shines | Internal team tool (same as Projection). | A polished, multi-company, customer-facing product with logins and billing. |

**Pick Streamlit now.** It matches the Projection Tool (same team, same deploy, same look) and handles long
runs and large PDFs without extra infrastructure. If this later becomes a product sold to other investors or
title companies, the agent core (`analyzer/`) is plain Python and can sit behind a FastAPI service with a
Vercel front end, with no change to the agent itself.

Hosting: Streamlit Community Cloud (private app, invited team only), like Projection. Data lives in a Postgres
database (Neon or Supabase, `DATABASE_URL`) and uploaded PDFs in private object storage (Supabase Storage or
S3). Nothing about deals is ever stored in the app's container or committed to git.

---

## 2. What the agent does with a commitment

A title commitment has a fixed shape, and the agent works through it in that shape so nothing is skipped:

| Part | What the agent pulls out | Why it matters for closing |
|---|---|---|
| **Schedule A** | Effective date, commitment #, policy amount(s), proposed insured, vested owner, estate/interest, legal description | Vesting must match the seller on the contract; amount vs price; stale effective date needs a bring-down |
| **Schedule B-I (Requirements)** | **Every numbered requirement**, word for word, with its page | Each one is a condition of the title company issuing the policy: all must be met or waived |
| **Schedule B-II (Exceptions)** | **Every numbered exception**, classified | Some must be removed before closing (mortgages, liens, judgments, "rights of parties in possession", survey exception if extended coverage is needed); standard ones are listed as acceptable |
| Notes, endorsements, cover letter, tax info | Tax status, HOA, chain of title notes, endorsements requested | Delinquent taxes, HOA estoppel, missing endorsements |

### The pipeline (each run)

1. **Read** – Extract text page by page (PyMuPDF). Scanned PDFs go to the model as images, so OCR quality isn't
   a weak point. Keep page numbers for every line.
2. **Structure** – The model returns Schedule A fields and the full list of B-I and B-II items with their
   numbers, page and exact wording (structured JSON output).
3. **Count check (deterministic, code, not AI)** – The code reads the numbering itself ("1.", "2.", "a.", …)
   and confirms the model found every item. Any gap (e.g. B-I item 7 missing) is sent back to the model
   until the counts match. **This is the core of "never leave an item behind."**
4. **Turn items into actions** – For each requirement and each exception that must be cleared, the agent writes
   the action, who's responsible (Seller, Buyer, Title Co., Lender, TC/Wholesaler, Attorney), what document
   satisfies it (payoff letter, release, affidavit, estoppel, death certificate, LLC resolution, …), and a
   priority:
   - **Closing Blocker** – the deal cannot fund/record until done.
   - **Before Closing** – needed by closing day, not a blocker today.
   - **Review / FYI** – acceptable as is, listed so the team sees it.
5. **Professional checklist pass** – Independent of what the commitment says, the agent runs a fixed list of
   checks a seasoned agent does on every file (Section 3). This is where "hidden" items surface: name mismatch,
   deceased owner, stale effective date, missing spouse signature, etc.
6. **Second-opinion pass** – A separate reviewer call gets the commitment + the draft list and is asked only
   one thing: *"What would stop this deal from closing that isn't on this list?"* New finds are added and
   marked "found on review".
7. **Lessons applied** – Every approved lesson from training and feedback (Section 4) is part of the agent's
   instructions on every run.
8. **Proof for every item** – Each item carries the page number and the exact quote it came from. Code checks
   the quote really appears on that page; an item that can't be traced is flagged, not silently dropped.

**Coverage panel on the results page:** `B-I Requirements 9 / 9 addressed · B-II Exceptions 14 / 14 classified
· Pro Checklist 32 / 32 run`. If anything is short of 100%, the page says so in red and the export carries a
warning line.

> Honest limit: no AI or human can promise zero misses on every file. This design makes a miss **visible**
> (counts must match), **traceable** (page + quote), **double-checked** (second pass) and **fixable for good**
> (one feedback click becomes a rule for every future deal). A person still signs off before closing.

---

## 3. The professional checklist (runs on every deal, editable in Settings)

Grouped as the output list is grouped. Starting set, to be refined with the team:

- **Vesting & parties** – Vested owner = seller on contract (exact spelling, middle names, suffixes); married
  seller → spouse joinder / homestead; owner deceased → probate, letters of administration, death certificate,
  heirship affidavit; trust → trust certificate + trustee authority; LLC/Corp → good standing, operating
  agreement, signing resolution; POA → recorded POA, not revoked; divorce → decree, quitclaim from ex-spouse.
- **Money liens** – Open mortgages / HELOCs (payoff letter + release); judgments (payoff or name affidavit
  if "similar name"); federal/state tax liens; child-support liens; mechanics' liens; municipal / code
  violation liens; utility liens; UCC fixture filings; lis pendens / foreclosure in progress.
- **Taxes & HOA** – Delinquent or current-year taxes, tax sale certificates, special assessments; HOA / condo
  estoppel, transfer fees, right of first refusal.
- **Property & survey** – Legal description matches contract and deed; survey exception (needs survey to
  remove); encroachments, easements, access / landlocked; parties in possession / tenants (leases, estoppels).
- **Commitment itself** – Effective date age (bring-down if old); policy amount vs purchase price; proposed
  insured matches buyer / assignee entity; endorsements needed.
- **Investor deal structure** (Total Cash Home Buyers specific) – Assignment of contract allowed and fee
  disclosed; double close: two commitments / A-B and B-C, transactional funding requirements, seasoning
  rules; novation / listing deals: listing agreement and seller authority; cash vs lender (lender adds its own
  requirements); 1031 / entity buyer docs.
- **Closing docs** – Owner's affidavit, non-foreign (FIRPTA) affidavit, 1099-S info, gap indemnity, ID for
  all signers, wiring instructions verification.

---

## 4. Training: how the agent learns

"Training" here means building the agent's **professional knowledge base**, not retraining an AI model. That
keeps it instant (a lesson works on the very next deal), reviewable, and reversible.

### Training area (Training tab)
1. Upload a commitment (or several) that a pro has already worked.
2. Type the list the pro would make, or paste / upload it (CSV, Excel, Word). The grid has the same columns
   as the output, so it's quick.
3. Click **Compare With Agent**. The agent runs on the same document and the app shows three columns:
   - ✅ **Both found** – matched items.
   - ❌ **Agent missed** – each becomes a **suggested lesson** ("When B-II lists a 'Notice of Commencement',
     require a final contractor's affidavit and lien waiver").
   - ➕ **Agent extra** – mark as *good catch* or *not needed* (also a lesson).
4. An admin approves, edits or rejects each suggested lesson. Approved lessons go live.
5. The example itself is kept. When a new deal looks similar (same county, same issue type, same structure),
   the most similar worked examples are shown to the agent as references.

### Feedback on live deals
- **Report Missing Item** button on every results page: what's missing, where it is in the document
  (page / schedule item, optional), why it would block closing, category. One minute to fill in.
- Per item: 👍 / **Not Needed** / **Wrong Info** with an optional note.
- All of it lands in the **Knowledge → Feedback Inbox** as suggested lessons, same approval flow.

### Knowledge tab
- **Lessons** – every rule the agent follows, with who added it, when, from which deal, and how many times
  it has fired since. On / off switch per lesson.
- **Worked Examples** – the training documents with their expert lists.
- **Scorecard** – re-runs the agent on all worked examples after every lesson change: *"Agent finds 97% of
  expert items (was 91% a month ago)"*. A lesson that makes the score drop is flagged before it goes live.

---

## 5. The output list

One row per action item. Same columns everywhere (screen, CSV, Sheets, PDF, Docs):

| # | Priority | Category | Item | Action Needed | Responsible | Source | Status | Notes |
|---|---|---|---|---|---|---|---|---|
| 1 | Closing Blocker | Liens | Open mortgage to ABC Bank, Inst. #2019-0045512 | Order payoff letter; record release at closing | Title Co. | B-I #4 · p.3 | Open | |

Header block on every export: property address, commitment #, effective date, proposed insured, policy amount,
generated date, coverage line (9/9 · 14/14 · 32/32), "Reviewed by: ______".

### Exports
| Format | How |
|---|---|
| **CSV** | Built in, one click download. |
| **Excel** | One click (.xlsx), with priority colors. |
| **PDF** | Branded closing checklist (logo, header block, grouped by priority, tick boxes), print ready. |
| **Word (.docx)** | Same layout as the PDF, editable. |
| **Google Sheets** | Creates a new sheet in the team's shared Drive folder and opens it. |
| **Google Docs** | Creates a new doc in the same folder and opens it. |

Google: one service account with **Content Manager** on a Shared Drive folder (e.g. "Title Checklists").
Service accounts no longer get their own Drive storage, so files must be created in a Shared Drive the team
owns. Every file it creates is then owned by the team, not by the app. (Alternative: "Sign in with Google"
so files land in each user's own Drive; more setup, decide in review.)

---

## 6. Screens

Same frame as the Projection Tool: glass sidebar (logo, "Title Agent", theme toggle, recent deals), tab capsule
at the top.

1. **Analyze** – Upload commitment (+ optional purchase contract to check vesting / price / buyer against),
   deal fields (address, deal type: Wholesale / Double Close / Novation / Fix & Flip / Buy & Hold), **Analyze**.
   Progress steps shown while it runs.
2. **Results** – Tiles (Closing Blockers, Before Closing, Review, Coverage %), coverage meter, the list
   grouped by priority (status and notes editable in place), source quote on click, **Export** menu,
   **Report Missing Item** button.
3. **Deals** – Every analyzed commitment, searchable; open status counts; re-run with the latest lessons.
4. **Training** – Section 4.
5. **Knowledge** – Lessons, Worked Examples, Feedback Inbox, Scorecard.
6. **Settings** – Pro checklist editor, responsible-party list, Google folder, retention period, users.

---

## 7. Under the hood

- **AI model**: Claude Opus 5.5 (`claude-opus-5-5`) through the official Anthropic Python SDK, adaptive
  thinking with effort set to `high` for this correctness-critical work, streaming responses, refusal
  fallback enabled. PDFs go in natively (text + page images, up to 600 pages / 32 MB per request).
  Structured JSON output for the item list. The fixed parts of the instructions (pro checklist + approved
  lessons) are prompt-cached, so repeat runs are cheaper and faster.
- **Estimated cost**: roughly $0.50–$2 per commitment depending on length and passes (to be measured on real
  files in week 1).
- **Code layout** (mirrors Projection):
  ```
  app.py                    entry, navigation, brand
  ui/                       brand.css, brand.py (copied from Projection), layout, html helpers
  views/                    analyze.py, results.py, deals.py, training.py, knowledge.py, settings.py
  analyzer/
    extract.py              PDF → pages (text, page images)
    structure.py            Schedule A / B-I / B-II parsing (model) + numbering check (code)
    actions.py              items → action list
    checklist.py            professional checklist pass
    review.py               second-opinion pass
    verify.py               quote/page grounding, coverage counts
    knowledge.py            lessons, examples, similarity lookup
  exports/                  csv_xlsx.py, pdf.py, docx.py, google.py
  storage.py                Postgres (deals, items, feedback, lessons, examples) + object storage
  tests/                    numbering check, coverage math, exports, a set of sample commitments
  ```
- **Privacy** (same spirit as Projection's non-negotiables): commitments contain names, addresses and loan
  numbers. Private storage only, team-only app, retention setting (e.g. delete PDFs after 12 months),
  never in git, logs or test fixtures. Anthropic API traffic is not used for model training.

---

## 8. Build plan

| Week | Deliverable |
|---|---|
| 1 | Skeleton app in TCHB theme; upload → extract → Schedule A / B-I / B-II structure with the numbering check. Test on 5–10 real commitments from the team. |
| 2 | Action list, pro checklist pass, second-opinion pass, grounding check; results page with coverage panel. |
| 3 | Exports (CSV, Excel, PDF, Word, Google Sheets, Google Docs); Deals history; Report Missing Item + per-item feedback. |
| 4 | Training tab, Knowledge tab (lessons approval, worked examples, scorecard); deploy; team trial. |

**What I need from you to start:** 5–10 real (or redacted) commitments with the list your team actually
worked from for each (those become the first training set and the accuracy test); which states/counties you
close in most; the title companies you use most (their commitment formats differ); and who approves lessons.

## 9. Open questions for review
1. Streamlit (recommended) or Vercel?
2. Google exports: Shared Drive folder (recommended) or each user signs in with Google?
3. Should a purchase contract upload be part of v1 (lets the agent check vesting, price and buyer against the
   commitment), or later?
4. Who can approve lessons: one admin, or anyone on the team?
5. How long should uploaded commitments be kept?
