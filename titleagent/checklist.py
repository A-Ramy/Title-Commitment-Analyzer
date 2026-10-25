"""The professional checklist: checks a seasoned title agent runs on every file, whatever the commitment says.

Each check names what to look for. The agent reports a finding only when the check turns something up; the
coverage panel counts every check that applied to the deal as run. Checks scoped to deal types run only there.
"""

from __future__ import annotations

from dataclasses import dataclass

ALL = "all"
INVESTOR = ("Wholesale (Assignment)", "Double Close", "Novation / Listing")
CREATIVE = ("Subject-To", "Seller Financing")


@dataclass(frozen=True)
class Check:
    id: str
    group: str
    name: str
    look_for: str
    deal_types: tuple[str, ...] | str = ALL

    def applies(self, deal_type: str) -> bool:
        return self.deal_types == ALL or deal_type in self.deal_types


CHECKS: list[Check] = [
    # ---- vesting and parties
    Check("V1", "Vesting & Parties", "Seller matches vested owner",
          "Contract seller(s) vs Schedule A vested owner: exact spelling, middle names and initials, suffixes, "
          "a/k/a variations, every co-owner present. A spelling difference anywhere in the chain (deed vs death "
          "certificate) needs a name affidavit or corrective instrument."),
    Check("V2", "Vesting & Parties", "Deceased owner or co-owner",
          "Any owner in the chain who died: estate opened? personal representative / executor authority, letters, "
          "probate or heirship, transfer-on-death affidavit, surviving spouse / survivorship affidavit, death "
          "certificate recorded, Medicaid estate recovery, estate tax release where the state requires it."),
    Check("V3", "Vesting & Parties", "Spouse joinder and homestead",
          "Married seller: spouse must sign or the deed must state the property is not homestead (homestead and "
          "marital-property states). Divorce: decree and quitclaim from the former spouse."),
    Check("V4", "Vesting & Parties", "Trust, POA, guardianship",
          "Trust: certificate of trust and trustee authority. Power of attorney: recorded, durable, not revoked, "
          "principal alive. Guardianship / conservatorship: court order authorizing the sale."),
    Check("V5", "Vesting & Parties", "Recent transfers and chain of title",
          "Transfers inside 24 months (flips, same-day double deeds, corrective deeds, PR deeds, quitclaims, tax "
          "deeds, sheriff's deeds): gaps, wild deeds, defects that need curative work or a seasoning answer."),
    Check("V6", "Vesting & Parties", "Prior-owner and same-name liens",
          "Judgments or liens against a prior owner or a similar name: payoff/release, or a name (identity) "
          "affidavit if it is a different person."),
    # ---- entities
    Check("E1", "Entity & Authority", "Seller entity authority",
          "LLC / corporation seller: active and in good standing, articles, operating agreement, who may sign, "
          "resolution or incumbency, bankruptcy of the entity or sole member."),
    Check("E2", "Entity & Authority", "Buyer / proposed insured entity",
          "Proposed insured named correctly and completely (state of organization filled in, no blank lines, "
          "no 'tenants by the entirety' for an entity), formation documents and signing authority."),
    Check("E3", "Entity & Authority", "FinCEN, OFAC, foreign ownership",
          "FinCEN residential real estate report (cash or non-bank-financed purchase by an entity or trust): "
          "beneficial-owner details due by closing. OFAC hits. State foreign-ownership restrictions. FIRPTA if a "
          "seller is a foreign person."),
    # ---- money owed against the property
    Check("M1", "Money Liens & Judgments", "Open mortgages and HELOCs",
          "Every open mortgage / deed of trust / HELOC (including MERS and assignments): payoff letter and recorded "
          "release; HELOC frozen and closed in writing."),
    Check("M2", "Money Liens & Judgments", "Foreclosure, lis pendens, bankruptcy",
          "Lis pendens, pending foreclosure case, sheriff's sale date, bankruptcy filing: reinstatement or payoff "
          "with dismissal, court approval, docket checked right before closing."),
    Check("M3", "Money Liens & Judgments", "Judgments",
          "Money judgments against owners (current and prior): payoff and satisfaction, or name affidavit."),
    Check("M4", "Money Liens & Judgments", "Government liens",
          "Federal tax liens (IRS), state tax liens and tax warrants, workers' compensation and unemployment liens, "
          "child support liens, Medicaid liens: payoff and certificate of release."),
    Check("M5", "Money Liens & Judgments", "Municipal and code liens",
          "Code enforcement, maintenance / demolition / weed / board-up liens, blight tickets, special "
          "assessments, municipal utility (water, sewer, trash) charges that become liens."),
    Check("M6", "Money Liens & Judgments", "Mechanics' and contractor liens",
          "Mechanics' liens, notices of commencement, recent repairs: final lien waivers, contractor's affidavit, "
          "termination of notice of commencement."),
    Check("M7", "Money Liens & Judgments", "UCC and solar / equipment filings",
          "UCC fixture filings, solar panel leases or loans, water heater / HVAC leases recorded against the land."),
    # ---- taxes
    Check("T1", "Taxes & Assessments", "Delinquent and current taxes",
          "Delinquent or unpaid installments, penalties, current-year taxes due before closing, prorations."),
    Check("T2", "Taxes & Assessments", "Tax certificates and tax sales",
          "Tax lien certificates, taxes sold to a third party (certificate of delinquency), tax sale redemption "
          "deadlines, tax deeds in the chain."),
    Check("T3", "Taxes & Assessments", "Unallocated or split parcels",
          "Taxes covering a larger parent parcel, a new parcel number, land division approvals."),
    # ---- HOA
    Check("H1", "HOA & Association", "HOA / condo estoppel",
          "Association dues, special assessments, estoppel or payoff letter, transfer fees, association approval "
          "of the buyer, right of first refusal."),
    # ---- property
    Check("P1", "Property & Survey", "Parties in possession and leases",
          "Tenants or occupants: leases, tenant estoppels, vacancy confirmation; recorded memoranda of lease or "
          "option that must be terminated."),
    Check("P2", "Property & Survey", "Recorded agreements to terminate",
          "Recorded memoranda of agreement, options, rights of first refusal, wind / solar / oil and gas leases, "
          "land contracts or contracts for deed: termination or release, or accept as an exception."),
    Check("P3", "Property & Survey", "Legal description, access, survey",
          "Legal description matches the contract and is insurable; access to a public road; survey exception if "
          "the buyer or lender needs it removed; land division / subdivision approvals."),
    Check("P4", "Property & Survey", "Manufactured home",
          "Manufactured / mobile home on the land: title retired or affixed to real property, VIN."),
    # ---- the commitment itself
    Check("C1", "Commitment Itself", "Commitment age and deadline",
          "Commitment date age (bring-down if old) and the deadline to meet all requirements (most are 180 days, "
          "some only 30)."),
    Check("C2", "Commitment Itself", "Policy amounts",
          "Owner's policy amount vs purchase price; loan policy amount vs loan; increases needed."),
    Check("C3", "Commitment Itself", "Errors and blanks",
          "Blanks ('______'), misspelled names, wrong entity type, wrong county or address, typos the title "
          "company must correct before closing."),
    # ---- closing documents
    Check("D1", "Closing Documents", "Seller closing documents",
          "Owner's / vendor's affidavit, gap indemnity, FIRPTA non-foreign affidavit, 1099-S information, state "
          "transfer forms (sales disclosure, transfer declarations), IDs for every signer."),
    Check("D2", "Closing Documents", "Funds and wiring",
          "Good-funds rules, wire requirements, verified wiring instructions."),
    # ---- investor structures
    Check("I1", "Investor Deal Structure", "Assignment of contract",
          "Contract allows assignment; assignment agreement and fee disclosure; proposed insured = end buyer.",
          INVESTOR),
    Check("I2", "Investor Deal Structure", "Double close (A-B / B-C)",
          "Two deeds: seller to our entity, our entity to end buyer; both legs insured or handled; transactional "
          "funding; end buyer funds in before the A-B leg records; our entity's documents.",
          ("Double Close",)),
    Check("I3", "Investor Deal Structure", "Novation / listing authority",
          "Seller's written authority (novation or listing agreement), seller signs the final deed, no interest "
          "taken by us, disclosures.", ("Novation / Listing",)),
    # ---- creative finance
    Check("F1", "Creative Finance", "Subject-to: existing loan",
          "Existing loan stays: current statement, reinstatement figure if behind, seller's authorization to "
          "release loan information, due-on-sale disclosure signed by the seller, insurance moved to the new owner "
          "with the lender as loss payee, servicing / payment plan, title to insure with the mortgage as an "
          "exception.", ("Subject-To",)),
    Check("F2", "Creative Finance", "Seller financing: note and mortgage",
          "Promissory note and mortgage / deed of trust from buyer to seller recorded at closing; terms match the "
          "contract; lender-licensing (Dodd-Frank / SAFE Act) where the buyer will live there; seller's own "
          "mortgage paid off or a wrap disclosed.", ("Seller Financing",)),
]

GROUPS = list(dict.fromkeys(c.group for c in CHECKS))


def for_deal(deal_type: str) -> list[Check]:
    return [c for c in CHECKS if c.applies(deal_type)]


def as_prompt() -> str:
    """Every check, with the deal types it is limited to. The same text on every call, so it stays cached; the
    step's task names the deal type."""
    lines = []
    for c in CHECKS:
        scope = "" if c.deal_types == ALL else f" [only for: {', '.join(c.deal_types)}]"
        lines.append(f"- [{c.id}] {c.name} ({c.group}){scope}: {c.look_for}")
    return "\n".join(lines)
