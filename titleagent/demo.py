"""A made-up sample deal (fictional names, numbers and places) for the developer preview (TITLE_AGENT_DEMO=1) and the
tests: a small commitment PDF plus the answers the AI would give, so the whole pipeline runs without an API key."""

from __future__ import annotations

import io
import textwrap

from titleagent.llm import ScriptedLLM
from titleagent.models import (
    ActionItemOut,
    ActionsOut,
    CompareOut,
    DispositionOut,
    EntryOut,
    MatchOut,
    PolicyOut,
    ReviewOut,
    ScheduleAOut,
    SourceOut,
    StructureOut,
)

REQUIREMENTS = [
    "Pay the agreed amount for the estate or interest to be insured.",
    "Pay the premiums, fees, and charges for the Policy to the Company.",
    "Warranty Deed from Linda M. Sample, a widow, to the Proposed Insured.",
    "Payment in full and release of record of Mortgage from Robert A. Sample and Linda M. Sample to First Example "
    "Bank, in the original amount of $142,000.00, recorded as Instrument No. 2018-0045512.",
    "Payment and release of Open-End Mortgage to Second Sample Credit Union, recorded as Instrument No. "
    "2021-0103377.",
    "Furnish a certified copy of the death certificate of Robert A. Sample, together with an Affidavit of "
    "Survivorship, to be recorded.",
    "Satisfaction or release of Judgment in favor of Demo Collections LLC against Robert Sample, Case No. "
    "21-CV-0331, in the amount of $8,214.00, or proof that the judgment debtor is not the same party.",
    "Disclose the name of the proposed insured and furnish evidence of its authority.",
    "Payment of all taxes and assessments which are due and payable.",
]
EXCEPTIONS = [
    "Taxes and assessments for the year 2026 and subsequent years, a lien not yet due and payable.",
    "Rights or claims of parties in possession not shown by the public records.",
    "Encroachments, overlaps, boundary line disputes, and any other matters which would be disclosed by an "
    "accurate survey.",
    "Easement to Demo Power Co., recorded as Instrument No. 1988-0004410.",
    "Covenants, conditions and restrictions as shown on the recorded plat of Maple Ridge, Plat Book 61, Page 22.",
    "Oil, gas and mineral rights reserved in deed recorded in Volume 211, Page 409.",
    "Declaration of Covenants for Maple Ridge, recorded as Instrument No. 1999-0012345, including assessments and "
    "lien rights of the Association.",
    "2025 taxes, 2nd half, DELINQUENT in the amount of $1,986.40 plus penalty and interest.",
]


def sample_commitment_pdf() -> bytes:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)

    def page(lines: list[str]) -> None:
        y = 740
        for line in lines:
            c.setFont("Helvetica-Bold" if line.isupper() else "Helvetica", 10)
            for n, part in enumerate(textwrap.wrap(line, 95)):
                c.drawString(50 if n == 0 else 64, y, part)
                y -= 14
            y -= 4
        c.showPage()

    page(["SAMPLE COMMITMENT FOR TITLE INSURANCE (MADE-UP DATA)", "SCHEDULE A",
          "Commitment Number: SMP-26-08812", "1. Commitment Date: August 14, 2026",
          "2. Policy to be issued: Owner's Policy. Proposed Insured: To Be Determined. Amount: $95,000.00",
          "3. The estate or interest in the Land is Fee Simple.",
          "4. The Title is vested in: Robert A. Sample and Linda M. Sample, husband and wife.",
          "5. The Land: Lot 14, Maple Ridge, Franklin County, Ohio. 1427 Maple Ave, Columbus OH 43206.",
          "If all of the Schedule B, Part I Requirements have not been met within 180 days after the Commitment "
          "Date, this Commitment terminates."])
    page(["SCHEDULE B, PART I - REQUIREMENTS", "All of the following Requirements must be met:",
          *[f"{n}. {t}" for n, t in enumerate(REQUIREMENTS, 1)]])
    page(["SCHEDULE B, PART II - EXCEPTIONS", *[f"{n}. {t}" for n, t in enumerate(EXCEPTIONS, 1)]])
    c.save()
    return buf.getvalue()


def structure() -> StructureOut:
    return StructureOut(
        schedule_a=ScheduleAOut(
            commitment_number="SMP-26-08812", commitment_date="2026-08-14", requirements_deadline_days=180,
            underwriter="Sample Title Insurance Co.", issuing_agent="Sample Title Agency",
            property_address="1427 Maple Ave, Columbus, OH 43206", county="Franklin", state="OH",
            policies=[PolicyOut(policy_type="owner", proposed_insured="To Be Determined", amount=95000.0)],
            estate="Fee Simple", vested_owner="Robert A. Sample and Linda M. Sample, husband and wife",
            legal_description_summary="Lot 14, Maple Ridge, Franklin County, Ohio"),
        requirements=[EntryOut(number=str(n), page=2, text=t) for n, t in enumerate(REQUIREMENTS, 1)],
        exceptions=[EntryOut(number=str(n), page=3, text=t) for n, t in enumerate(EXCEPTIONS, 1)],
        notes=[], scanned_pages=[], contract=None, suggested_deal_type="Double Close")


def _item(priority, category, title, action, provided_by, due_rule, ref, page, quote, amount=None, why=""):
    return ActionItemOut(priority=priority, category=category, title=title, action=action, provided_by=provided_by,
                         amount=amount, due_rule=due_rule, why=why or "Title will not insure until this is done.",
                         sources=[SourceOut(ref=ref, page=page, quote=quote)])


def actions() -> ActionsOut:
    items = [
        _item("blocker", "Vesting & Parties", "Vested owner Robert A. Sample is deceased",
              "Record the certified death certificate and an Affidavit of Survivorship before the deed.", "Seller",
              "curative", "B-I 6", 2, "Furnish a certified copy of the death certificate of Robert A. Sample"),
        _item("blocker", "Money Liens & Judgments", "Open mortgage to First Example Bank, $142,000",
              "Order the payoff letter; pay from proceeds; record the release.", "Lender / Servicer", "payoff",
              "B-I 4", 2, "release of record of Mortgage from Robert A. Sample and Linda M. Sample to First Example "
              "Bank", 142000.0),
        _item("blocker", "Money Liens & Judgments", "Open-end mortgage (HELOC) to Second Sample Credit Union",
              "Payoff letter plus a closure letter signed by the borrower so the line can't be drawn again.",
              "Lender / Servicer", "payoff", "B-I 5", 2, "release of Open-End Mortgage to Second Sample Credit Union"),
        _item("blocker", "Money Liens & Judgments", "Judgment: Demo Collections LLC v. Robert Sample, $8,214",
              "Pay and record the satisfaction, or get a name affidavit if it is a different Robert Sample.",
              "Lienholder / Creditor", "payoff", "B-I 7", 2, "Judgment in favor of Demo Collections LLC against "
              "Robert Sample", 8214.0),
        _item("blocker", "Commitment Itself", "Proposed insured is \"To Be Determined\"",
              "Give the title company the end buyer's entity name and have the commitment updated.", "Our Team",
              "documents", "B-I 8", 2, "Disclose the name of the proposed insured"),
        _item("before", "Taxes & Assessments", "Delinquent 2025 2nd-half taxes, $1,986.40 + penalty",
              "Get the county treasurer's payoff; pay from the seller's proceeds at closing.", "County / City",
              "closing", "B-II 8", 3, "2025 taxes, 2nd half, DELINQUENT in the amount of $1,986.40", 1986.40),
        _item("before", "HOA & Association", "Maple Ridge HOA: estoppel and dues",
              "Order the estoppel letter; pay dues and transfer fee at closing.", "HOA / Association", "documents",
              "B-II 7", 3, "Declaration of Covenants for Maple Ridge"),
        _item("before", "Commitment Itself", "Commitment date Aug 14, 2026 is getting old",
              "Order a bring-down (title update) within 10 days of closing.", "Title Company / Attorney",
              "bring_down", "Sch A 1", 1, "Commitment Date: August 14, 2026"),
        _item("before", "Commitment Itself", "Owner's policy $95,000 is below the purchase price",
              "Ask the title company to raise the policy amount to the price.", "Title Company / Attorney",
              "documents", "Sch A 2", 1, "Amount: $95,000.00"),
        _item("before", "Closing Documents", "Warranty deed from Linda M. Sample, a widow",
              "Title prepares the deed to the A-B buyer entity; seller signs at closing.", "Title Company / Attorney",
              "closing", "B-I 3", 2, "Warranty Deed from Linda M. Sample, a widow"),
        _item("fyi", "Property & Survey", "Utility easement to Demo Power Co.",
              "Standard; stays on the policy.", "Other", "none", "B-II 4", 3, "Easement to Demo Power Co."),
        _item("fyi", "Property & Survey", "Oil, gas and mineral rights reserved",
              "FYI for the buyer; does not stop closing.", "Other", "none", "B-II 6", 3,
              "Oil, gas and mineral rights reserved"),
    ]
    disp = ([DispositionOut(ref=f"B-I {n}", handling=h, note="") for n, h in
             zip(range(1, 10), ["routine", "routine", "action", "action", "action", "action", "action", "action",
                                "action"], strict=True)]
            + [DispositionOut(ref=f"B-II {n}", handling=h, note="") for n, h in
               zip(range(1, 9), ["acceptable", "routine", "acceptable", "acceptable", "acceptable", "acceptable",
                                 "action", "action"], strict=True)])
    return ActionsOut(items=items, dispositions=disp, checklist_findings=["Deceased owner or co-owner",
                                                                          "Commitment age and deadline"])


def second_review() -> ReviewOut:
    return ReviewOut(missing_items=[
        _item("before", "Investor Deal Structure", "Double close: second commitment for the B-C leg",
              "Order the B-C commitment; confirm transactional funding or end-buyer funds before the A-B leg records.",
              "Title Company / Attorney", "documents", "Checklist: Double close (A-B / B-C)", None, ""),
    ], corrections=[])


def compare_answer() -> CompareOut:
    return CompareOut(matches=[MatchOut(expert_index=0, agent_index=1, lesson=""),
                               MatchOut(expert_index=1, agent_index=None,
                                        lesson="When the property has a pool or recent permits, ask for the final "
                                               "inspection sign-off before closing.")],
                      extra_agent_indexes=[4])


def scripted_llm() -> ScriptedLLM:
    return ScriptedLLM({"structure": structure(), "actions": actions(), "review": second_review(),
                        "compare": compare_answer()})
