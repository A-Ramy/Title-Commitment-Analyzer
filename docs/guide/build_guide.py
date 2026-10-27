"""Builds the branded Title Agent user guide (PDF) for the TCs and the Owner.

    uv run python docs/guide/build_guide.py      ->  docs/guide/Title_Agent_User_Guide.pdf

Screenshots in docs/guide/shots/ come from the app with made-up sample deals (titleagent/demo.py), never real ones.
Fonts: Baloo 2 and Nunito Sans (SIL Open Font License), the same as the app.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    CondPageBreak,
    Frame,
    Image,
    KeepTogether,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
SHOTS = HERE / "shots"
CROPS = HERE / ".crops"  # cropped copies of the screenshots, rebuilt each time (gitignored)
OUT = HERE / "Title_Agent_User_Guide.pdf"
LOGO = ROOT / "assets" / "logo-full.png"
LOGO_WHITE = ROOT / "assets" / "logo-full-white.png"

# brand (ui/brand.py)
INDIGO, RED, GREEN = colors.HexColor("#4D458A"), colors.HexColor("#BD2239"), colors.HexColor("#109648")
INK, BODY, MUTED = colors.HexColor("#211E33"), colors.HexColor("#47445A"), colors.HexColor("#767388")
LAV, ACCENT_SOFT, LINE = colors.HexColor("#F2F1F9"), colors.HexColor("#EAE9F4"), colors.HexColor("#DDDBEA")
WARN_BG, WARN = colors.HexColor("#FFF3D1"), colors.HexColor("#8A5A00")
BAD_BG, GOOD_BG, ORANGE = colors.HexColor("#FBF0F2"), colors.HexColor("#EAF7EF"), colors.HexColor("#B45309")
ORANGE_BG = colors.HexColor("#FFF1E0")

PAGE_W, PAGE_H = letter
MARGIN = 0.75 * inch
WIDTH = PAGE_W - 2 * MARGIN


def fonts() -> None:
    f = HERE / "fonts"
    for name, file in (("Baloo", "Baloo2-700.ttf"), ("Baloo-Semi", "Baloo2-600.ttf"), ("Nunito", "NunitoSans-400.ttf"),
                       ("Nunito-Semi", "NunitoSans-600.ttf"), ("Nunito-Bold", "NunitoSans-700.ttf"),
                       ("Nunito-Italic", "NunitoSans-400i.ttf"), ("Nunito-Black", "NunitoSans-800.ttf")):
        pdfmetrics.registerFont(TTFont(name, str(f / file)))
    pdfmetrics.registerFont(TTFont("DejaVu", str(f / "DejaVuSans.ttf")))  # ✓ ✗ ★ →, missing from the brand fonts
    pdfmetrics.registerFontFamily("Nunito", normal="Nunito", bold="Nunito-Bold", italic="Nunito-Italic",
                                  boldItalic="Nunito-Bold")


fonts()
S = {
    "h1": ParagraphStyle("h1", fontName="Baloo", fontSize=22, leading=26, textColor=INDIGO, spaceAfter=4),
    "h2": ParagraphStyle("h2", fontName="Baloo", fontSize=14.5, leading=18, textColor=INDIGO, spaceBefore=10,
                         spaceAfter=3, keepWithNext=1),
    "lead": ParagraphStyle("lead", fontName="Nunito", fontSize=11, leading=16, textColor=BODY, spaceAfter=8),
    "p": ParagraphStyle("p", fontName="Nunito", fontSize=10, leading=14.5, textColor=BODY, spaceAfter=6),
    "small": ParagraphStyle("small", fontName="Nunito", fontSize=8.5, leading=11.5, textColor=MUTED),
    "cap": ParagraphStyle("cap", fontName="Nunito-Italic", fontSize=8.5, leading=11, textColor=MUTED,
                          alignment=TA_CENTER, spaceBefore=3, spaceAfter=10),
    "cell": ParagraphStyle("cell", fontName="Nunito", fontSize=9, leading=12, textColor=BODY),
    "cellb": ParagraphStyle("cellb", fontName="Nunito-Bold", fontSize=9, leading=12, textColor=INK),
    "th": ParagraphStyle("th", fontName="Nunito-Bold", fontSize=9, leading=12, textColor=colors.white),
    "step": ParagraphStyle("step", fontName="Nunito", fontSize=10, leading=14.5, textColor=BODY),
    "toc": ParagraphStyle("toc", fontName="Nunito-Semi", fontSize=11, leading=20, textColor=INK),
}


# ---------------------------------------------------------------- building blocks
SYMBOLS = "✓✗★→"


def Para(text: str, style: ParagraphStyle, **kw) -> Paragraph:
    for ch in SYMBOLS:
        text = text.replace(ch, f'<font name="DejaVu">{ch}</font>')
    return Paragraph(text, style, **kw)


def P(text: str, style: str = "p") -> Paragraph:
    return Para(text, S[style])


def section(n: int, title: str, lead: str = "", need: float = 3.2) -> list:
    """need: inches the heading and what follows it need, or it starts on a new page."""
    badge = Table([[Para(f'<font name="Nunito-Black" color="white">{n}</font>',
                              ParagraphStyle("b", fontSize=11, leading=13, alignment=TA_CENTER))]],
                  colWidths=[0.32 * inch], rowHeights=[0.32 * inch])
    badge.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), RED), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                               ("ROUNDEDCORNERS", [5, 5, 5, 5]), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                               ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    head = Table([[badge, Para(title, S["h1"])]], colWidths=[0.45 * inch, WIDTH - 0.45 * inch])
    head.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                              ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
    head.keepWithNext = True
    out = [CondPageBreak(need * inch), head]
    if lead:
        intro = P(lead, "lead")
        intro.keepWithNext = True
        out.append(intro)
    return out


def steps(items: list[str]) -> Table:
    rows = []
    for i, t in enumerate(items, 1):
        num = Table([[Para(f'<font name="Nunito-Black" color="#4D458A">{i}</font>',
                                ParagraphStyle("n", fontSize=9.5, leading=11, alignment=TA_CENTER))]],
                    colWidths=[0.24 * inch], rowHeights=[0.24 * inch])
        num.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), ACCENT_SOFT), ("ROUNDEDCORNERS", [12, 12, 12, 12]),
                                 ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                 ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0),
                                 ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
        rows.append([num, Para(t, S["step"])])
    t = Table(rows, colWidths=[0.38 * inch, WIDTH - 0.38 * inch])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 5), ("TOPPADDING", (0, 0), (-1, -1), 1)]))
    return t


def bullets(items: list[str]) -> list:
    return [Para(t, ParagraphStyle("bl", parent=S["p"], leftIndent=12, bulletIndent=2, spaceAfter=3),
                      bulletText="•") for t in items]


def box(text: str, kind: str = "tip", title: str = "") -> Table:
    bg, edge, label = {"tip": (ACCENT_SOFT, INDIGO, "Tip"), "warn": (WARN_BG, WARN, "Important"),
                       "bad": (BAD_BG, RED, "Watch out"), "good": (GOOD_BG, GREEN, "Good to know")}[kind]
    content = Para(f'<font name="Nunito-Bold" color="{edge.hexval()}">{title or label}.</font> {text}', S["p"])
    t = Table([[content]], colWidths=[WIDTH])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), bg), ("ROUNDEDCORNERS", [8, 8, 8, 8]),
                           ("LEFTPADDING", (0, 0), (-1, -1), 12), ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                           ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                           ("LINEBEFORE", (0, 0), (0, -1), 3, edge)]))
    return KeepTogether([Spacer(1, 3), t, Spacer(1, 7)])


def table(head: list[str], rows: list[list[str]], widths: list[float], first_bold: bool = True) -> Table:
    data = [[Para(h, S["th"]) for h in head]]
    for r in rows:
        data.append([Para(c, S["cellb"] if (i == 0 and first_bold) else S["cell"]) for i, c in enumerate(r)])
    t = Table(data, colWidths=[w * WIDTH for w in widths], repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), INDIGO), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LAV]),
                           ("LINEBELOW", (0, 1), (-1, -1), 0.4, LINE), ("ROUNDEDCORNERS", [8, 8, 8, 8]),
                           ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                           ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7)]))
    return KeepTogether([t, Spacer(1, 8)])


def shot(name: str, caption: str, width: float = 1.0, crop: tuple[float, float, float, float] | None = None,
         max_h: float = 4.6) -> KeepTogether:
    """A screenshot with a thin frame. crop = (left, top, right, bottom) as fractions of the image."""
    CROPS.mkdir(exist_ok=True)
    im = PILImage.open(SHOTS / f"{name}.png").convert("RGB")
    if crop:
        w, h = im.size
        im = im.crop((int(crop[0] * w), int(crop[1] * h), int(crop[2] * w), int(crop[3] * h)))
    if im.width > 1700:  # about 240 dpi across the page: sharp in print, light enough to email
        im = im.resize((1700, round(im.height * 1700 / im.width)), PILImage.LANCZOS)
    src = CROPS / f"{name}-{'-'.join(f'{c:.2f}' for c in (crop or (0, 0, 1, 1)))}.jpg"
    im.save(src, quality=82, optimize=True)
    pw, ph = im.size
    w = WIDTH * width
    h = w * ph / pw
    if h > max_h * inch:  # keep tall shots on one page
        h = max_h * inch
        w = h * pw / ph
    img = Image(str(src), width=w, height=h)
    frame = Table([[img]], colWidths=[w + 6])
    frame.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.6, LINE), ("ROUNDEDCORNERS", [6, 6, 6, 6]),
                               ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                               ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    return KeepTogether([Spacer(1, 4), frame, P(caption, "cap")])


# ---------------------------------------------------------------- pages
def cover(c, doc) -> None:
    c.saveState()
    c.setFillColor(LAV)
    c.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)
    # soft brand glows, like the app background
    for x, y, r, col, alpha in ((0.05, 1.02, 4.2, INDIGO, 0.10), (1.0, 0.95, 3.4, RED, 0.06),
                                (0.6, -0.05, 3.8, GREEN, 0.05)):
        c.setFillColor(col, alpha=alpha)
        c.circle(x * PAGE_W, y * PAGE_H, r * inch, stroke=0, fill=1)
    c.setFillColor(INDIGO)
    c.rect(0, 0, PAGE_W, 1.15 * inch, stroke=0, fill=1)
    c.drawImage(str(LOGO), MARGIN, PAGE_H - 2.55 * inch, width=3.9 * inch, height=3.9 * inch * 274 / 900, mask="auto")
    c.setFillColor(INDIGO)
    c.setFont("Baloo", 40)
    c.drawString(MARGIN, PAGE_H - 4.15 * inch, "Title Agent")
    c.setFont("Baloo-Semi", 24)
    c.setFillColor(RED)
    c.drawString(MARGIN, PAGE_H - 4.6 * inch, "User Guide")
    c.setFont("Nunito", 13)
    c.setFillColor(BODY)
    y = PAGE_H - 5.25 * inch
    for line in ("How to review a title commitment, work the list,",
                 "and get every deal to the closing table.",):
        c.drawString(MARGIN, y, line)
        y -= 19
    c.setFont("Nunito-Bold", 11)
    c.setFillColor(INK)
    c.drawString(MARGIN, PAGE_H - 6.35 * inch, "For: Transaction Coordinators and the Owner")
    c.setFont("Nunito", 10)
    c.setFillColor(MUTED)
    c.drawString(MARGIN, PAGE_H - 6.62 * inch, f"Version 1 · {date.today():%B %Y}")
    c.setFillColor(colors.white)
    c.setFont("Nunito-Bold", 9.5)
    c.drawString(MARGIN, 0.62 * inch, "Total Cash Home Buyers · Internal use only")
    c.setFont("Nunito", 9)
    c.drawRightString(PAGE_W - MARGIN, 0.62 * inch, "Screens show made-up sample deals")
    c.restoreState()


def inner(c, doc) -> None:
    c.saveState()
    c.drawImage(str(LOGO), MARGIN, PAGE_H - 0.62 * inch, width=1.25 * inch, height=1.25 * inch * 274 / 900,
                mask="auto")
    c.setFont("Nunito-Semi", 8.5)
    c.setFillColor(MUTED)
    c.drawRightString(PAGE_W - MARGIN, PAGE_H - 0.5 * inch, "Title Agent · User Guide")
    c.setStrokeColor(LINE)
    c.setLineWidth(0.6)
    c.line(MARGIN, PAGE_H - 0.72 * inch, PAGE_W - MARGIN, PAGE_H - 0.72 * inch)
    c.line(MARGIN, 0.62 * inch, PAGE_W - MARGIN, 0.62 * inch)
    c.drawString(MARGIN, 0.42 * inch, "Total Cash Home Buyers · Internal use only")
    c.setFillColor(INDIGO)
    c.setFont("Nunito-Bold", 9)
    c.drawRightString(PAGE_W - MARGIN, 0.42 * inch, str(doc.page))
    c.restoreState()


SECTIONS = [
    "What The Title Agent Does", "Signing In", "Finding Your Way Around", "Reviewing A New Commitment",
    "Reading The Results", "Working The List Every Day", "Checking Where An Item Comes From",
    "When The Agent Misses Something", "Updated Commitments And Re-Runs", "Exporting The List",
    "Deals And The Daily Email", "For The Owner And Admins", "Good Habits", "Quick Answers",
]


def story() -> list:
    s: list = [NextPageTemplate("inner"), PageBreak()]

    # ---- contents
    s += [P("Contents", "h1"), Spacer(1, 6)]
    toc = [[Para(f'<font name="Baloo" color="#BD2239">{i}</font>', S["toc"]), Para(t, S["toc"])]
           for i, t in enumerate(SECTIONS, 1)]
    toc.append([Para('<font name="Baloo" color="#BD2239">★</font>', S["toc"]),
                Para("Quick Reference Card (last page)", S["toc"])])
    t = Table(toc, colWidths=[0.4 * inch, WIDTH - 0.4 * inch])
    t.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE), ("TOPPADDING", (0, 0), (-1, -1), 3),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 3), ("LEFTPADDING", (0, 0), (-1, -1), 2)]))
    s += [t, Spacer(1, 14),
          box("TCs: read sections 1–11 and keep the Quick Reference Card handy. Owner: also read section 12.",
              "tip", "Who reads what")]
    s.append(PageBreak())

    # ---- 1
    s += section(1, "What The Title Agent Does",
                 "Upload a title commitment, and the Title Agent lists everything that has to happen before the deal "
                 "can close, the way a senior title examiner would. Each item shows exactly where it came from, so "
                 "you can check it in seconds.")
    cards = [
        ("Reads every page", "Including scanned pages. It reads Schedule A, every Schedule B-I requirement and every "
                             "B-II exception, plus the purchase contract if you add it."),
        ("Leaves nothing behind", "A separate check (not the AI) counts every numbered item in the commitment. If "
                                  "anything is unaccounted for, the screen tells you in red."),
        ("Learns from your team", "When it misses something, you report it. Once an admin approves the lesson, the "
                                  "agent checks for it on every deal from then on."),
    ]
    cw = (WIDTH - 0.3 * inch) / 3
    row = []
    for title, text in cards:
        cell = Table([[Para(title, ParagraphStyle("ct", fontName="Baloo", fontSize=12.5, leading=15,
                                                       textColor=INDIGO))],
                      [Para(text, S["cell"])]], colWidths=[cw - 0.1 * inch])
        cell.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
        row.append(cell)
    ct = Table([row], colWidths=[cw + 0.1 * inch] * 3)
    ct.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), LAV), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("LINEAFTER", (0, 0), (1, 0), 4, colors.white), ("ROUNDEDCORNERS", [8, 8, 8, 8]),
                            ("LEFTPADDING", (0, 0), (-1, -1), 10), ("TOPPADDING", (0, 0), (-1, -1), 9),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 9)]))
    s += [ct, Spacer(1, 10)]
    s += [P("What a review gives you", "h2")]
    s += bullets([
        "<b>A list sorted by urgency</b>: Closing Blockers first, then Before Closing, then Review / FYI.",
        "<b>For every item</b>: what to do, who actually has to provide it, a due date counted back from closing, the "
        "amount when there is one, and the exact wording and page in the commitment.",
        "<b>Warnings</b> when the commitment expires before your closing date, or when a numbered item could not be "
        "accounted for.",
        "<b>A working checklist</b>: statuses, due dates and notes the whole team sees, exportable to Excel, PDF, Word "
        "and more.",
    ])
    s += [box("The Title Agent does not replace the title company or the attorney, and it can be wrong. It makes "
              "sure nothing is overlooked. A person still checks the list and signs off before closing.", "warn")]

    # ---- 2
    s += section(2, "Signing In", "The app is on the web, so it asks who you are before it shows anything.")
    s += [steps([
        "Open the app link the Owner sent you. Bookmark it.",
        "Type your <b>work email</b> and the <b>team password</b>, then click <b>Sign In</b>.",
        "That's it for the next 30 days on that browser. Refreshing the page or clicking a link from the daily "
        "email opens straight in.",
        "On a shared or public computer, click <b>Sign Out</b> at the bottom of the left sidebar when you're done.",
    ]), shot("01-signin", "The sign-in screen. Nothing else in the app is visible until you sign in.", 0.62,
             crop=(0.22, 0.04, 0.78, 0.68))]
    s += [box("Never share the team password outside the company, and never paste it into email threads with "
              "sellers, buyers or title companies. If it leaks, the Owner changes it and everyone signs in again.",
              "bad")]
    s += [box("The first visit of the day can take about 30 seconds while the app wakes up. That's normal.", "tip")]

    # ---- 3
    s += section(3, "Finding Your Way Around", need=5.3)
    s += [shot("02-home", "The Analyze page right after signing in.", 1.0)]
    s += [table(["Where", "What it's for"], [
        ["Tabs at the top", "<b>Analyze</b>: upload a commitment. <b>Deals</b>: every deal reviewed. "
                            "<b>Training</b>: teach the agent (optional). <b>Knowledge</b>: what the agent knows."],
        ["Open Deals (sidebar)", "Your open deals with their open Closing Blockers count. Click one to jump to it."],
        ["Knowledge (n)", "The number shows feedback waiting for an admin."],
        ["Settings", "Team setup: admins, TCs, email recipients, due-date rules (admins only)."],
        ["Light / Dark", "Switches the look. Your choice is remembered."],
        ["Signed in as / Sign Out", "Who you are in the app. Your name is recorded on what you change."],
    ], [0.27, 0.73])]

    # ---- 4
    s += section(4, "Reviewing A New Commitment",
                 "When the title company sends a commitment, run it through the agent before you do anything else.")
    s += [steps([
        "Click the <b>Analyze</b> tab.",
        "Under <b>Title commitment (PDF)</b>, click <b>Upload</b> and pick the PDF. Scanned PDFs are fine.",
        "Optional but recommended: upload the <b>Purchase contract (PDF)</b>. The agent then checks the seller, "
        "buyer, price and dates against the commitment.",
        "Leave <b>Is this an updated commitment…</b> on <b>No, a new deal</b> (for revised commitments see section 9).",
        "Click <b>Read Documents</b>. Reading takes about a minute.",
    ]), shot("15-analyze", "Step 1: upload the commitment (and the contract if you have it).", 1.0,
             crop=(0.24, 0.0, 1.0, 0.45))]
    s += [P("Confirm the deal", "h2"),
          P("The agent fills in the deal details from the documents. Check each one and fix anything that's off:")]
    s += [table(["Field", "What to check"], [
        ["Property address / State", "Matches the contract."],
        ["Deal type", "Wholesale (Assignment), Double Close, Novation / Listing, Fix &amp; Flip, Buy &amp; Hold, "
                      "Subject-To or Seller Financing. It changes which checks the agent runs, so get it right."],
        ["Closing date", "Every due date is counted back from it. If you don't know it yet, add it later and re-run."],
        ["TC", "Who owns this deal's list."],
        ["Title company", "Usually filled in from the commitment."],
        ["Notes for the agent", "Anything it can't see in the documents, e.g. \"seller is behind on payments\"."],
    ], [0.27, 0.73])]
    s += [shot("16-confirm", "Step 2: confirm what the agent read, then click Run Full Review.", 1.0,
               crop=(0.24, 0.1, 1.0, 1.0))]
    s += [steps([
        "Look at the box above the form. Green <b>Numbering check passed</b> means every numbered requirement and "
        "exception was picked up. Red lists the item numbers to check by hand.",
        "Click <b>Run Full Review</b>. It takes 1–3 minutes: the agent writes the list, then a second, independent "
        "pass looks only for anything missing. You land on the deal page when it's done.",
    ])]
    s += [box("<b>Start Over</b> throws away this upload and takes you back to the upload screen. Nothing is "
              "saved as a deal until you click Run Full Review.", "tip")]

    # ---- 5
    s += section(5, "Reading The Results",
                 "The deal page is where you'll spend your time. Read it top to bottom the first time.")
    s += [shot("03-deal-top", "The top of a deal page: summary, coverage, actions and the start of the list.", 1.0,
               crop=(0.22, 0.0, 1.0, 1.0))]
    s += [P("The summary tiles", "h2")]
    s += [table(["Tile", "Meaning"], [
        ["Closing Blockers", "Open items that stop the closing. Red until they're all cleared."],
        ["Before Closing", "Open items needed by closing day, handled in the normal course."],
        ["Review / FYI", "Standard exceptions and notes, listed so nothing is hidden. No action needed."],
        ["Coverage", "100% means every numbered item in Schedule B-I and B-II was accounted for."],
        ["Days To Closing", "Counts down to the closing date."],
    ], [0.27, 0.73])]
    s += [P("The coverage bar", "h2"),
          P("Three green bars mean the agent accounted for every <b>B-I requirement</b> and every "
            "<b>B-II exception</b>, and ran the professional checklist (31–34 checks depending on the deal type). If any bar is short or "
            "there's a red <b>Check by hand</b> box, open the commitment and read those item numbers yourself.")]
    s += [box("If you see <b>The commitment expires before closing</b>, ask the title company for an updated "
              "commitment right away. Some commitments expire 30 days after their date, not 180.", "bad")]
    s += [P("The three priorities", "h2")]
    s += [table(["Priority", "What it means", "Typical examples"], [
        ['<font color="#BD2239">Closing Blocker</font>',
         "Needs money paid to, or a document from, someone outside the closing table, or a court / government "
         "action. The deal can't close until it's done.",
         "Mortgage payoffs and releases, lis pendens / foreclosure, judgments (even a prior owner's), tax lien "
         "certificates, city and state tax liens, workers' comp liens, code and maintenance liens, delinquent "
         "utilities, wind/lease/option memoranda to terminate, errors in the commitment."],
        ['<font color="#B45309">Before Closing</font>',
         "Needed by closing day, but handled in the normal course.",
         "The deed, LLC documents, FinCEN details, HOA estoppel, affidavits, transfer forms, bring-down of an old "
         "commitment, taxes due paid at closing."],
        ['<font color="#4D458A">Review / FYI</font>',
         "Standard exceptions that stay on the policy, and notes. Glance at them.",
         "Utility easements, plat restrictions, mineral rights, road rights of way, taxes not yet due."],
    ], [0.18, 0.37, 0.45])]
    s += [P("The item list", "h2"),
          shot("04-blockers", "Closing Blockers on a sample deal.", 1.0)]
    s += [table(["Column", "Meaning"], [
        ["Item &amp; Action Needed", "The headline in bold, then exactly what to order, pay, sign or record."],
        ["Provided By", "Who actually holds or provides it (seller, lender, county, court…). <b>Owner</b> is always "
                        "the deal's TC, who chases it."],
        ["Due", "Counted back from the closing date (see section 6). Weekends move to the Friday before."],
        ["Amount", "When the commitment shows one."],
        ["Source", "Where it comes from: <b>B-I 4 · p.2</b> means Schedule B-I item 4 on page 2. "
                   "<b>✓</b> the quoted wording was found on that page. <b>·</b> scanned page or a checklist item, "
                   "not checkable. <b>✗</b> not found word for word: open the source and check."],
        ["Status", "Open, Ordered, Received, Cleared or Waived, plus your notes."],
    ], [0.24, 0.76])]

    # ---- 6
    s += section(6, "Working The List Every Day",
                 "The list is the team's live checklist. Keep it current and everyone (and the daily email) stays "
                 "in sync.")
    s += [shot("06-editor", "Below the list: update Status, Due and Notes. Changes save as soon as you make them.",
               1.0)]
    s += [steps([
        "Scroll below the list to <b>Update Status, Due Dates And Notes</b>.",
        "Click a <b>Status</b> cell and pick the new status.",
        "Click a <b>Due</b> cell to change the date, or a <b>Notes</b> cell to type a note (e.g. "
        "\"Payoff requested from servicer 10/26\").",
        "Press Enter or click elsewhere. It saves immediately; there's no Save button.",
    ])]
    s += [table(["Status", "Use it when"], [
        ["Open", "Nothing has been done yet."],
        ["Ordered", "You've requested it (payoff letter ordered, estoppel requested, affidavit sent for signature)."],
        ["Received", "You have it, but title hasn't confirmed it's satisfied yet."],
        ["Cleared", "Done. Title confirmed, or it's recorded or paid. Cleared items fade in the list."],
        ["Waived", "Not needed after all (e.g. the buyer accepts it on the policy). Add a note saying why."],
    ], [0.18, 0.82])]
    s += [P("How due dates are set", "h2")]
    s += [table(["Kind of item", "Due before closing"], [
        ["Payoff letters and lien payoffs", "10 days"],
        ["Court, estate and curative work (terminations, corrections)", "14 days"],
        ["Documents (affidavits, entity docs, forms)", "5 days"],
        ["Bring-down of the commitment", "5 days"],
        ["Paid or signed at the closing table", "Closing day"],
    ], [0.7, 0.3])]
    s += [box("Use the <b>Show</b> buttons above the list: <b>Open Only</b> hides what's done, <b>Blockers</b> "
              "shows just the Closing Blockers. A good daily routine: open each deal, filter to Open Only, work "
              "anything due in the next 3 days, update statuses.", "tip")]

    # ---- 7
    s += section(7, "Checking Where An Item Comes From",
                 "Never take an item on faith. Every item quotes the commitment so you can check it fast.")
    s += [steps([
        "On the deal page, click <b>Where each item comes from (exact wording)</b>.",
        "Each card shows the priority, the source (e.g. <b>B-I 6 · p.2</b>), why it matters, and the exact quote.",
        "To double-check, open the commitment PDF to that page. The original PDFs are under "
        "<b>Documents and review history</b> at the bottom of the deal page.",
    ]), shot("07-sources", "Every item with its quote from the commitment.", 0.8, crop=(0.0, 0.0, 1.0, 0.47),
             max_h=4.3)]

    # ---- 8
    s += section(8, "When The Agent Misses Something",
                 "This is how the agent gets better. Report every miss, even small ones.")
    s += [steps([
        "On the deal page, click <b>Report Missing Item</b>.",
        "Fill in <b>What's missing</b>, <b>Where in the document</b> (e.g. B-II #10, page 9) and <b>Why it would "
        "stop or delay the closing</b>.",
        "Pick the <b>Priority</b> and <b>Who has to provide it</b>. Leave <b>Add it to this deal's list now</b> "
        "ticked so it goes straight onto your list.",
        "Click <b>Send Feedback</b>. It goes to the Owner's Feedback Inbox. Once approved, the agent checks for it "
        "on every deal.",
    ]), shot("10-report-missing", "Report Missing Item.", 0.82)]
    s += [P("Something on the list is wrong or not needed?", "h2"),
          P("Open <b>Feedback on an item</b> at the bottom of the deal page, pick the item, choose <b>Not Needed</b> "
            "or <b>Wrong Info</b>, add a short note and click <b>Send</b>. Then set the item's status to "
            "<b>Waived</b> with a note."),
          shot("08-item-feedback", "Feedback on a single item.", 0.82)]

    # ---- 9
    s += section(9, "Updated Commitments And Re-Runs")
    s += [P("When the title company sends a revised commitment", "h2")]
    s += [steps([
        "On the deal page, click <b>Updated Commitment</b> (or go to Analyze).",
        "Upload the new PDF and, under <b>Is this an updated commitment…</b>, pick the deal.",
        "Click <b>Read Documents</b>, check the details, then <b>Run Full Review</b>.",
        "Your statuses and notes carry over. New items are marked <b>New</b>; items the title company took off "
        "move to <b>Removed by the title company</b>, crossed out.",
    ])]
    s += [P("Re-Run Review", "h2"),
          P("<b>Re-run Review</b> reads the same commitment again with the latest lessons, for example after the "
            "Owner approves new lessons or you added a closing date. Statuses and notes are kept.")]

    # ---- 10
    s += section(10, "Exporting The List",
                 "Send the checklist to the title company, the seller or the buyer, or keep a copy with the file.")
    s += [steps([
        "On the deal page, click <b>Export List</b>.",
        "Leave <b>Include Review / FYI items</b> on to send everything, or turn it off to send only items that "
        "need action.",
        "Click the format: <b>CSV</b>, <b>Excel</b>, <b>PDF</b> or <b>Word</b>. The file downloads with the "
        "property address in its name.",
    ]), shot("09-export", "The export menu.", 0.95, crop=(0.22, 0.0, 0.75, 0.62))]
    s += [box("<b>Google Sheets</b> and <b>Google Docs</b> appear in the same menu once the Owner connects Google "
              "Drive. Files are then created in the team's shared folder.", "tip")]
    s += [box("Exports contain names, addresses and loan numbers. Send them only to people on the deal.", "warn")]

    # ---- 11
    s += section(11, "Deals And The Daily Email")
    s += [P("The Deals page", "h2"),
          P("Every reviewed deal, newest first, with its TC, title company, open blockers, open items and anything "
            "overdue. Search by address, TC, title company or commitment number; switch between <b>Open</b>, "
            "<b>Closed</b> and <b>All</b>; click <b>Open</b> to go to the deal."),
          shot("11-deals", "The Deals page.", 1.0, crop=(0.22, 0.0, 1.0, 0.72))]
    s += [P("Closing out a deal", "h2"),
          P("After it closes, open <b>Documents and review history</b> at the bottom of the deal page and click "
            "<b>Mark Deal Closed</b>. It leaves the open list and the daily email. <b>Reopen Deal</b> brings it "
            "back.")]
    s += [P("The daily email", "h2"),
          P("Every weekday morning, everyone on the list gets one email from <b>title-agent@totalchb.com</b>, covering "
            "every open deal: its open Closing Blockers and anything due in the next 3 days, with overdue items "
            "flagged and an <b>Open</b> link straight to the deal.")]

    # ---- 12
    s += section(12, "For The Owner And Admins",
                 "Admins approve what the agent learns and set up the team. Admins are listed in Settings.")
    s += [P("Approving lessons (Knowledge tab)", "h2"),
          shot("12-knowledge", "The Feedback Inbox: edit the lesson, then approve or reject.", 1.0,
               crop=(0.22, 0.0, 1.0, 0.86))]
    s += [steps([
        "Open <b>Knowledge</b>. The sidebar shows how many items are waiting.",
        "Read each item in the <b>Feedback Inbox</b>. The suggested lesson is in the text box.",
        "Edit it into a <b>general rule</b> the agent can apply to every commitment. Good: \"When a city lists "
        "unpaid water or sewer charges, order a final read and list the payoff as a Closing Blocker.\" Bad: names, "
        "addresses, amounts or case numbers from one deal.",
        "Click <b>Approve Lesson</b> (it applies from the next review) or <b>Reject</b>.",
    ])]
    s += [P("Under <b>Lessons</b>, every active lesson has an on/off switch. Turn one off if it causes wrong items; "
            "add your own with <b>Add a lesson</b>. The first 10 lessons came from the 8 worked commitments the team "
            "provided.")]
    s += [CondPageBreak(3.6 * inch), P("Settings", "h2")]
    s += [table(["Setting", "What to put"], [
        ["Admins", "Emails of the people who approve lessons and change settings, one per line. Type them exactly "
                   "as those people type their email at sign-in."],
        ["TCs", "Names (or emails) of the TCs, one per line. You pick from this list when confirming a deal."],
        ["Daily Email: Send to", "Everyone who gets the morning summary."],
        ["Daily Email: Send from", "title-agent@totalchb.com (leave as is)."],
        ["Due Dates", "Days before closing for each kind of item (defaults: payoffs 10, curative 14, documents 5, "
                      "bring-down 5, closing 0)."],
        ["Shared Drive folder ID", "For Google Sheets / Docs exports, once Google is connected."],
    ], [0.27, 0.73])]
    s += [shot("13-settings", "Settings. Click Save Settings when done; the Connections tiles below show what's "
                              "connected.", 1.0, crop=(0.22, 0.0, 1.0, 1.0), max_h=4.2)]
    s += [box("Admins are recognized by the email typed at sign-in. Keep the team password to the team, and "
              "change it (in Streamlit → Settings → Secrets → APP_PASSWORD) when someone leaves. Changing it signs "
              "everyone out.", "warn")]
    s += [P("Training (optional)", "h2"),
          P("To measure the agent, upload a commitment your team already worked on the <b>Training</b> tab, paste "
            "the closer's list and click <b>Compare With Agent</b>. You'll see what both found, what the agent "
            "missed (each becomes a suggested lesson in the inbox) and what it added. Each comparison is a full "
            "review: 1–3 minutes and roughly $1–2 in AI usage.")]

    # ---- 13
    s += section(13, "Good Habits")
    s += bullets([
        "<b>Run every commitment through the agent</b> the day it arrives, and every revised commitment too.",
        "<b>Always add the closing date.</b> Without it, there are no due dates and no countdown.",
        "<b>Check the coverage bar.</b> Anything short of 100% or a red box means: read those items yourself.",
        "<b>Check every ✗ in the Source column</b> against the commitment.",
        "<b>Keep statuses current.</b> The daily email and the whole team rely on them.",
        "<b>Report every miss.</b> One report can save every future deal.",
        "<b>Keep deal data inside the company.</b> Don't forward exports or the app link outside the team.",
        "<b>A person signs off</b> on the list before closing. The agent helps; it doesn't decide.",
    ])

    # ---- 14
    s += section(14, "Quick Answers")
    s += [table(["Question", "Answer"], [
        ["The app is slow to open.", "It sleeps when nobody uses it. The first visit wakes it in about 30 seconds."],
        ["It asks for the password again.", "You signed out, cleared cookies, used a different browser, or the "
                                            "Owner changed the password."],
        ["\"The AI service is busy\" or another error.", "Wait a minute and click the button again. Your upload is "
                                                          "kept until you click Start Over."],
        ["The numbering check is red.", "Read the listed item numbers in the commitment yourself and add anything "
                                        "missing with Report Missing Item."],
        ["An item is wrong.", "Feedback on an item → Wrong Info, then set it to Waived with a note."],
        ["I picked the wrong deal type or date.", "Upload the commitment again as an updated commitment for that "
                                                  "deal and fix the details on the confirm screen."],
        ["Can I upload a scanned PDF?", "Yes. Quotes from scanned pages show · instead of ✓, because there's no text "
                                        "to check them against."],
        ["Where are the original PDFs?", "Deal page → Documents and review history."],
        ["Who sees my changes?", "Everyone on the team, immediately. Your email is recorded on each change."],
    ], [0.34, 0.66])]

    # ---- reference card
    s += [PageBreak(), P("Quick Reference Card", "h1"), P("Print this page and keep it at your desk.", "lead")]
    ref = [
        ("New commitment", "Analyze → upload PDF (+ contract) → Read Documents → confirm deal type and closing "
                           "date → Run Full Review."),
        ("Revised commitment", "Deal → Updated Commitment → pick the deal → Read Documents → Run Full Review."),
        ("Every morning", "Read the daily email → open each deal → Show: Open Only → work what's due → update "
                          "statuses and notes."),
        ("Something's missing", "Deal → Report Missing Item → fill it in → Send Feedback."),
        ("Something's wrong", "Deal → Feedback on an item → Wrong Info / Not Needed → set status to Waived."),
        ("Send the list", "Deal → Export List → PDF / Word / Excel / CSV."),
        ("Deal closed", "Deal → Documents and review history → Mark Deal Closed."),
    ]
    s.append(table(["I want to…", "Do this"], [[a, b] for a, b in ref], [0.25, 0.75]))
    pri = Table([[Para('<font name="Nunito-Bold" color="#BD2239">Closing Blocker</font><br/>Stops the closing. '
                            'Payoffs, liens, judgments, court items.', S["cell"]),
                  Para('<font name="Nunito-Bold" color="#B45309">Before Closing</font><br/>Needed by closing '
                            'day. Deed, entity docs, estoppel, forms.', S["cell"]),
                  Para('<font name="Nunito-Bold" color="#4D458A">Review / FYI</font><br/>Stays on the policy. '
                            'Easements, restrictions, notes.', S["cell"])]],
                colWidths=[WIDTH / 3] * 3)
    pri.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, 0), BAD_BG), ("BACKGROUND", (1, 0), (1, 0), ORANGE_BG),
                             ("BACKGROUND", (2, 0), (2, 0), ACCENT_SOFT), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                             ("LINEAFTER", (0, 0), (1, 0), 4, colors.white), ("TOPPADDING", (0, 0), (-1, -1), 8),
                             ("BOTTOMPADDING", (0, 0), (-1, -1), 8), ("LEFTPADDING", (0, 0), (-1, -1), 9),
                             ("ROUNDEDCORNERS", [8, 8, 8, 8])]))
    s += [P("Priorities", "h2"), pri, Spacer(1, 8)]
    s.append(P("Statuses", "h2"))
    st = Table([[Para(f'<font name="Nunito-Bold">{a}</font><br/>{b}', S["cell"]) for a, b in
                 (("Open", "Not started"), ("Ordered", "Requested"), ("Received", "In hand"),
                  ("Cleared", "Done"), ("Waived", "Not needed + note"))]], colWidths=[WIDTH / 5] * 5)
    st.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), LAV), ("LINEAFTER", (0, 0), (3, 0), 3, colors.white),
                            ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                            ("ROUNDEDCORNERS", [8, 8, 8, 8])]))
    s += [st, Spacer(1, 8), P("Source marks", "h2"),
          P("<b>✓</b> quote found on the page · <b>·</b> scanned page or checklist item · <b>✗</b> check it yourself"),
          P("Due dates", "h2"),
          P("Payoffs 10 days before closing · court / curative 14 · documents 5 · bring-down 5 · paid at the table: "
            "closing day. Weekends move to the Friday before.")]
    return s


def build() -> Path:
    doc = BaseDocTemplate(str(OUT), pagesize=letter, title="Title Agent User Guide",
                          author="Total Cash Home Buyers", subject="How to use the Title Agent")
    cover_frame = Frame(MARGIN, MARGIN, WIDTH, PAGE_H - 2 * MARGIN, id="cover")
    body = Frame(MARGIN, 0.8 * inch, WIDTH, PAGE_H - 1.75 * inch, id="body")
    doc.addPageTemplates([PageTemplate("cover", [cover_frame], onPage=cover),
                          PageTemplate("inner", [body], onPage=inner)])
    doc.build([Spacer(1, 1), *story()])
    return OUT


if __name__ == "__main__":
    print(build())
