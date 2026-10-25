"""Data shapes. The *Out models are what the AI returns (structured output): every field is required and nullable
fields say so, so the JSON schema stays within what structured outputs support. The rest are the app's own shapes."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Priority = Literal["blocker", "before", "fyi"]
PRIORITY_LABEL = {"blocker": "Closing Blocker", "before": "Before Closing", "fyi": "Review / FYI"}
PRIORITY_ORDER = {"blocker": 0, "before": 1, "fyi": 2}

Category = Literal[
    "Money Liens & Judgments",
    "Taxes & Assessments",
    "Vesting & Parties",
    "Entity & Authority",
    "HOA & Association",
    "Property & Survey",
    "Commitment Itself",
    "Recording & Curative",
    "Investor Deal Structure",
    "Creative Finance",
    "Closing Documents",
    "Other",
]

ProvidedBy = Literal[
    "Seller",
    "Buyer",
    "End Buyer",
    "Title Company / Attorney",
    "Lender / Servicer",
    "Lienholder / Creditor",
    "HOA / Association",
    "County / City",
    "Court",
    "Contractor",
    "Our Team",
    "Other",
]

DueRule = Literal["payoff", "curative", "documents", "bring_down", "closing", "none"]

Handling = Literal[
    "action",  # turned into one or more action items
    "routine",  # standard requirement the closing agent satisfies in the normal course (deed, premium, ID...)
    "informational",  # a note, nothing to do
    "acceptable",  # standard exception that stays on the policy
    "needs_review",  # unusual: a person should read it
]

ItemStatus = Literal["Open", "Ordered", "Received", "Cleared", "Waived"]
STATUSES: list[str] = ["Open", "Ordered", "Received", "Cleared", "Waived"]
DONE_STATUSES = {"Cleared", "Waived"}


# ---------------------------------------------------------------- step 1: what the documents say


class PolicyOut(BaseModel):
    policy_type: Literal["owner", "loan", "other"]
    proposed_insured: str = Field(description="Exactly as written, including any blanks like '______'")
    amount: float | None


class ScheduleAOut(BaseModel):
    commitment_number: str
    commitment_date: str = Field(description="YYYY-MM-DD, or empty if not shown")
    requirements_deadline_days: int | None = Field(
        description="Days after the Commitment Date by which all Schedule B-I requirements must be met "
        "(from the 'Commitment to Issue Policy' paragraph), e.g. 180 or 30"
    )
    underwriter: str
    issuing_agent: str
    property_address: str
    county: str
    state: str = Field(description="Two-letter state code")
    policies: list[PolicyOut]
    estate: str
    vested_owner: str = Field(description="Exactly as written in Schedule A item 4, including any chain of title text")
    legal_description_summary: str


class EntryOut(BaseModel):
    number: str = Field(description="The item number exactly as printed, e.g. '7' or '1(4)'")
    page: int = Field(description="1-based PDF page where the item starts")
    text: str = Field(description="The complete wording of the item, verbatim")


class ContractOut(BaseModel):
    sellers: list[str]
    buyers: list[str]
    purchase_price: float | None
    closing_date: str = Field(description="YYYY-MM-DD, or empty")
    assignment_allowed: bool | None
    financing: str = Field(description="cash, conventional, hard money, seller financing, subject-to, ... or empty")
    notes: str


class StructureOut(BaseModel):
    schedule_a: ScheduleAOut
    requirements: list[EntryOut] = Field(description="Every numbered Schedule B, Part I item, in order")
    exceptions: list[EntryOut] = Field(description="Every numbered Schedule B, Part II item, in order")
    notes: list[EntryOut] = Field(description="Informational notes, tax notes and chain-of-title notes outside the "
                                  "numbered items (number them N1, N2, ...)")
    scanned_pages: list[int] = Field(description="Pages that are images with no selectable text")
    contract: ContractOut | None
    suggested_deal_type: str = Field(description="One of the deal types given, or empty")


# ---------------------------------------------------------------- step 2: what has to happen


class SourceOut(BaseModel):
    ref: str = Field(description="'B-I 7', 'B-II 14', 'Sch A 4', 'Note N2', 'Contract', or 'Checklist: <check name>'")
    page: int | None
    quote: str = Field(description="Exact words copied from that page (empty for checklist-only items)")


class ActionItemOut(BaseModel):
    priority: Priority
    category: Category
    title: str = Field(description="Short headline, e.g. 'Open mortgage to First Example Bank, $142,000'")
    action: str = Field(description="What has to be done and what document satisfies it")
    provided_by: ProvidedBy = Field(description="Who actually holds or provides what is needed")
    amount: float | None
    due_rule: DueRule
    why: str = Field(description="One sentence: why this matters for closing")
    sources: list[SourceOut]


class DispositionOut(BaseModel):
    ref: str = Field(description="'B-I <number>' or 'B-II <number>'")
    handling: Handling
    note: str


class ActionsOut(BaseModel):
    items: list[ActionItemOut]
    dispositions: list[DispositionOut] = Field(description="Exactly one per Schedule B-I and B-II item")
    checklist_findings: list[str] = Field(description="Professional checklist checks that found something, by name")


class ReviewOut(BaseModel):
    missing_items: list[ActionItemOut]
    corrections: list[str] = Field(description="Items on the list that look wrong, with the reason")


# ---------------------------------------------------------------- training comparison


class MatchOut(BaseModel):
    expert_index: int
    agent_index: int | None = Field(description="Index of the agent item covering it, or null if the agent missed it")
    lesson: str = Field(description="If missed: a general rule (no names, no amounts) that would have caught it")


class CompareOut(BaseModel):
    matches: list[MatchOut]
    extra_agent_indexes: list[int]


# ---------------------------------------------------------------- the app's own shapes


class Source(BaseModel):
    ref: str
    page: int | None = None
    quote: str = ""
    verified: bool | None = None  # quote found on that page; None = scanned page or nothing to check


class ActionItem(BaseModel):
    key: str  # stable within a deal (survives re-runs and updated commitments)
    priority: Priority
    category: str
    title: str
    action: str
    provided_by: str
    owner: str = "TC"
    amount: float | None = None
    due_rule: str = "none"
    due_date: str | None = None
    why: str = ""
    sources: list[Source] = []
    origin: Literal["commitment", "checklist", "contract", "review", "feedback"] = "commitment"
    status: str = "Open"
    notes: str = ""
    change: Literal["", "new", "removed"] = ""  # vs the previous commitment for this deal


class Coverage(BaseModel):
    requirements_total: int = 0
    requirements_addressed: int = 0
    exceptions_total: int = 0
    exceptions_addressed: int = 0
    checklist_total: int = 0
    checklist_run: int = 0
    unaddressed: list[str] = []
    numbering_gaps: list[str] = []  # numbers the text shows but the extraction lacked
    unverified_quotes: int = 0

    @property
    def complete(self) -> bool:
        return not self.unaddressed and not self.numbering_gaps

    @property
    def percent(self) -> int:
        total = self.requirements_total + self.exceptions_total
        done = self.requirements_addressed + self.exceptions_addressed
        return 100 if total == 0 else int(100 * done / total)


class Analysis(BaseModel):
    structure: StructureOut
    items: list[ActionItem]
    dispositions: list[DispositionOut]
    checklist_findings: list[str] = []
    corrections: list[str] = []
    coverage: Coverage
    usage: dict = {}
    lessons_applied: int = 0
