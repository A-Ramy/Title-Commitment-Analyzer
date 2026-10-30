"""Builds the branded Title Commitment Agent user guide (PDF) for the TCs and the Owner.

    uv run python docs/guide/build_guide.py      ->  docs/guide/Title_Commitment_Agent_User_Guide.pdf

Screenshots in docs/guide/shots/ come from the page on the local emulators with made-up sample deals
(titleagent/demo.py, TITLE_AGENT_DEMO=1), never real ones.
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
OUT = HERE / "Title_Commitment_Agent_User_Guide.pdf"
LOGO = ROOT / "web" / "public" / "logo-full.png"
APP = "Title Commitment Agent"

# brand (web/src/styles.css)
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
    im = PILImage.open(SHOTS / f"{name}.jpg").convert("RGB")
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


def pair(left: str, right: str, caption: str, height: float = 4.3) -> KeepTogether:
    """Two phone screenshots side by side."""
    cells = []
    for name in (left, right):
        w, h = PILImage.open(SHOTS / f"{name}.jpg").size
        cells.append(Image(str(SHOTS / f"{name}.jpg"), width=height * inch * w / h, height=height * inch))
    t = Table([cells], colWidths=[WIDTH / 2.6] * 2)
    t.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    return KeepTogether([Spacer(1, 4), t, P(caption, "cap")])


def flow() -> KeepTogether:
    """The Team Hub connection as a picture: what goes over, and what comes back."""
    def node(title: str, sub: str, bg) -> Table:
        t = Table([[Para(title, ParagraphStyle("nt", fontName="Baloo", fontSize=13, leading=15, textColor=INDIGO,
                                               alignment=TA_CENTER))],
                   [Para(sub, ParagraphStyle("ns", parent=S["cell"], alignment=TA_CENTER))]],
                  colWidths=[1.95 * inch])
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), bg), ("ROUNDEDCORNERS", [8, 8, 8, 8]),
                               ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
        return t

    arrow = ParagraphStyle("ar", parent=S["cell"], alignment=TA_CENTER)
    mid = Table([[Para('<font name="Nunito-Bold" color="#BD2239">Closing Blockers →</font><br/>'
                       'one task per deal, one subtask per blocker, with its action, source and due date', arrow)],
                 [Spacer(1, 6)],
                 [Para('<font name="Nunito-Bold" color="#109648">← ticked / unticked</font><br/>'
                       'a blocker ticked done there is Cleared here; unticked is Open again', arrow)]],
                colWidths=[2.3 * inch])
    t = Table([[node(APP, "title.totalchb.com<br/>where the list is worked", LAV), mid,
                node("Universal Team Hub", "hub.totalchb.com<br/>where the team's tasks live", ACCENT_SOFT)]],
              colWidths=[2.15 * inch, 2.7 * inch, 2.15 * inch])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (0, 0), (-1, -1), "CENTER")]))
    return KeepTogether([Spacer(1, 4), t, Spacer(1, 10)])


# ---------------------------------------------------------------- pages
def cover(c, doc) -> None:
    c.saveState()
    c.setFillColor(LAV)
    c.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)
    # soft brand glows, like the page's moving background
    for x, y, r, col, alpha in ((0.05, 1.02, 4.2, INDIGO, 0.10), (1.0, 0.95, 3.4, RED, 0.06),
                                (0.6, -0.05, 3.8, GREEN, 0.05)):
        c.setFillColor(col, alpha=alpha)
        c.circle(x * PAGE_W, y * PAGE_H, r * inch, stroke=0, fill=1)
    c.setFillColor(INDIGO)
    c.rect(0, 0, PAGE_W, 1.15 * inch, stroke=0, fill=1)
    lw, lh = PILImage.open(LOGO).size
    c.drawImage(str(LOGO), MARGIN, PAGE_H - 2.55 * inch, width=3.6 * inch, height=3.6 * inch * lh / lw, mask="auto")
    c.setFillColor(INDIGO)
    c.setFont("Baloo", 38)
    c.drawString(MARGIN, PAGE_H - 4.1 * inch, "Title Commitment")
    c.setFillColor(RED)
    c.drawString(MARGIN, PAGE_H - 4.65 * inch, "Agent")
    c.setFont("Baloo-Semi", 22)
    c.setFillColor(INDIGO)
    c.drawString(MARGIN, PAGE_H - 5.2 * inch, "User Guide")
    c.setFont("Nunito", 13)
    c.setFillColor(BODY)
    y = PAGE_H - 5.8 * inch
    for line in ("How to review a title commitment, work the list,",
                 "and get every deal to the closing table."):
        c.drawString(MARGIN, y, line)
        y -= 19
    c.setFont("Nunito-Bold", 11)
    c.setFillColor(INK)
    c.drawString(MARGIN, PAGE_H - 6.85 * inch, "For: Transaction Coordinators and the Owner")
    c.setFont("Nunito", 10)
    c.setFillColor(MUTED)
    c.drawString(MARGIN, PAGE_H - 7.12 * inch, f"Version 2.0 · {date.today():%B %Y} · title.totalchb.com")
    c.setFillColor(colors.white)
    c.setFont("Nunito-Bold", 9.5)
    c.drawString(MARGIN, 0.62 * inch, "Total Cash Home Buyers · Internal use only")
    c.setFont("Nunito", 9)
    c.drawRightString(PAGE_W - MARGIN, 0.62 * inch, "Screens show made-up sample deals")
    c.restoreState()


def inner(c, doc) -> None:
    c.saveState()
    lw, lh = PILImage.open(LOGO).size
    c.drawImage(str(LOGO), MARGIN, PAGE_H - 0.62 * inch, width=1.2 * inch, height=1.2 * inch * lh / lw, mask="auto")
    c.setFont("Nunito-Semi", 8.5)
    c.setFillColor(MUTED)
    c.drawRightString(PAGE_W - MARGIN, PAGE_H - 0.5 * inch, f"{APP} · User Guide")
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
    f"What The {APP} Does", "Signing In", "Finding Your Way Around", "Reviewing A New Commitment",
    "Reading A Deal", "Working The List Every Day", "When The Agent Misses Something",
    "Updated Commitments And Re-Runs", "Exporting The List", "The Universal Team Hub Connection",
    "Deals, Closing Out And The Daily Email", "For The Owner And Admins", "Good Habits", "Quick Answers",
]
DESK = (0.14, 0.0, 0.86, 1.0)  # the page's content column on a desktop screenshot


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
          box("TCs: read sections 1–11 and keep the Quick Reference Card handy. Owner and admins: also read "
              "section 12.", "tip", "Who reads what"),
          box(f"The Title Agent is now the <b>{APP}</b>, at <b>title.totalchb.com</b>. It looks and works like "
              "the Universal Team Hub, you sign in with your company Google account, and its Closing Blockers show "
              "up in the hub as tasks (section 10). Old links from earlier emails still open the right deal.",
              "good", "What's new in version 2")]
    s.append(PageBreak())

    # ---- 1
    s += section(1, f"What The {APP} Does",
                 f"Upload a title commitment, and the {APP} lists everything that has to happen before the deal "
                 "can close, the way a senior title examiner would. Each item shows exactly where it came from, so "
                 "you can check it in seconds.")
    cards = [
        ("Reads every page", "Including scanned pages. It reads Schedule A, every Schedule B-I requirement and every "
                             "B-II exception, plus the purchase contract if you add it."),
        ("Leaves nothing behind", "A separate check (code, not AI) counts every numbered item in the commitment. If "
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
        "<b>A live checklist</b> the whole team sees: statuses, due dates and notes change on everyone's screen at "
        "once. Export it to PDF, Word, Excel, CSV or Google Sheets / Docs.",
        "<b>The Closing Blockers in the Universal Team Hub</b>, kept in step both ways (section 10), and a summary "
        "email every weekday at 8:00 AM Eastern.",
    ])
    s += [box(f"The {APP} does not replace the title company or the attorney, and it can be wrong. It makes "
              "sure nothing is overlooked. A person still checks the list and signs off before closing.", "warn")]

    # ---- 2
    s += section(2, "Signing In", "Only company Google accounts (@totalchb.com) can open it. There is no "
                                  "separate password.")
    s += [steps([
        "Go to <b>title.totalchb.com</b> and bookmark it.",
        "Click <b>Sign In With Google</b> and pick your <b>@totalchb.com</b> account.",
        "You stay signed in on that browser. Links from the daily email and from the Team Hub open straight to "
        "the deal.",
        "On a shared computer, click your initials at the top right, then <b>Sign Out</b>.",
    ]), shot("01-signin", "The sign-in screen. Nothing else is visible until you sign in.", 0.78,
             crop=(0.14, 0.0, 0.86, 0.62))]
    s += [box("A personal Gmail or any other account is turned away with \"doesn't have access. Use your "
              "@totalchb.com account.\" Sign in again with your company account.", "tip")]

    # ---- 3
    s += section(3, "Finding Your Way Around", need=5.0)
    s += [shot("12-deals", "Deals, the home page: every open deal with its open Closing Blockers, days to closing and "
                           "how much of the list is done.", 1.0, crop=(0.14, 0.0, 0.86, 0.78))]
    s += [table(["Where", "What it's for"], [
        ["DEALS", "Home. Every reviewed deal, with search and Open / Closed / All. The numbers at the top count open "
                  "deals, open Closing Blockers and deals closing in the next 7 days."],
        ["ANALYZE", "Upload a new or updated commitment (section 4)."],
        ["TRAINING", "Optional: measure the agent on a commitment your team already worked (section 12)."],
        ["KNOWLEDGE", "What the agent knows: the Feedback Inbox, the team's lessons and the professional checklist."],
        ["Sun / moon", "Light or dark look. Your choice is remembered on that browser."],
        ["Your initials", "Your account (with <b>admin</b> if you are one), <b>Settings</b> and <b>Sign Out</b>."],
    ], [0.2, 0.8])]
    s += [shot("13-menu", "Click your initials for Settings and Sign Out.", 0.45, crop=(0.58, 0.0, 0.86, 0.25))]
    s += [P("On a phone", "h2"),
          P("Same link, same sign-in. The tabs move to a second row, every item is a card you tap to open, and menus "
            "slide up from the bottom. Everything works on a phone, uploads and exports included; a computer is "
            "easier for long lists."),
          pair("21-phone-deals", "22-phone-deal", "On a phone: the Deals page and a deal's Closing Blockers.")]

    # ---- 4
    s += section(4, "Reviewing A New Commitment",
                 "When the title company sends a commitment, run it through the agent before you do anything else.")
    s += [steps([
        "Click <b>ANALYZE</b> (or <b>Analyze A Commitment</b> on the Deals page).",
        "Drop the commitment PDF on <b>Title Commitment (PDF)</b>, or click it to choose the file. Scanned PDFs are "
        "fine (PDF only, under 50 MB).",
        "Optional but recommended: add the <b>Purchase Contract</b>. The agent then checks the seller, buyer, price "
        "and dates against the commitment.",
        "Leave <b>Is This An Updated Commitment…</b> on <b>No, a new deal</b> (revised commitments: section 8).",
        "Click <b>Read Documents</b>. It takes about a minute; the step it's on shows as it goes.",
    ]), shot("02-analyze", "Step 1: upload the commitment (and the contract if you have it).", 1.0,
             crop=(0.14, 0.12, 0.86, 0.72))]
    s += [P("Confirm the deal", "h2"),
          P("The agent fills in the deal details from the documents. Check each one and fix anything that's off:")]
    s += [table(["Field", "What to check"], [
        ["Property Address / State", "Matches the contract."],
        ["Deal Type", "Wholesale (Assignment), Double Close, Novation / Listing, Fix &amp; Flip, Buy &amp; Hold, "
                      "Subject-To or Seller Financing. It changes which checks the agent runs, so get it right."],
        ["Closing Date", "Every due date is counted back from it. If you don't know it yet, add it later and re-run."],
        ["TC (Owns Every Item)", "Who owns this deal's list. The names come from Settings."],
        ["Title Company", "Usually filled in from the commitment."],
        ["Notes For The Agent", "Anything it can't see in the documents, e.g. \"seller is behind on payments\"."],
    ], [0.27, 0.73])]
    s += [shot("03-confirm", "Step 2: confirm what the agent read, then click Run Full Review.", 0.95,
               crop=(0.14, 0.08, 0.86, 0.86), max_h=5.0)]
    s += [steps([
        "Look at the box at the top. Green <b>Numbering check passed</b> means every numbered requirement and "
        "exception was picked up. Red lists the item numbers to check by hand.",
        "Click <b>Run Full Review</b>. It takes 1–3 minutes: the agent writes the list, then a second, independent "
        "pass looks only for anything missing. You land on the deal when it's done.",
    ])]
    s += [box("You can keep working in another tab while it runs. If you refresh by mistake, the confirm screen "
              "comes back in the same tab. <b>Start Over</b> throws the upload away: nothing is saved as a deal "
              "until you click Run Full Review.", "tip")]

    # ---- 5
    s += section(5, "Reading A Deal",
                 "The deal page is where you'll spend your time. Read it top to bottom the first time.")
    s += [shot("04-deal-top", "The top of a deal: the summary, the actions and the start of the list.", 1.0,
               crop=(0.14, 0.12, 0.86, 1.0))]
    s += [table(["At the top", "Meaning"], [
        ["Deal type and Closing chip", "The chip counts the days to closing; it turns orange inside 7 days and red "
                                       "once the date has passed."],
        ["Open Blockers", "Closing Blockers not yet Cleared or Waived. Red until there are none."],
        ["Items Cleared", "Done (Cleared or Waived) out of everything on the list. The bar below fills up as you go."],
        ["Coverage", "100% means every numbered item in Schedule B-I and B-II was accounted for. Anything less comes "
                     "with a red <b>Check by hand</b> box naming the item numbers: read those yourself."],
    ], [0.27, 0.73])]
    s += [box("If you see <b>The commitment expires before closing</b>, ask the title company for an updated "
              "commitment right away. Some commitments expire 30 days after their date, not 180.", "bad")]
    s += [P("The three priorities", "h2")]
    s += [table(["Priority", "What it means", "Typical examples"], [
        ['<font color="#BD2239">Closing Blocker</font>',
         "Needs money paid to, or a document from, someone outside the closing table, or a court / government "
         "action. The deal can't close until it's done. These also go to the Team Hub.",
         "Mortgage payoffs and releases, lis pendens and pending foreclosures, judgments (even a prior owner's), "
         "tax lien certificates, taxes sold or certified as a lien, city and state tax liens, workers' comp liens, "
         "code and maintenance liens, delinquent utilities, wind/lease/option memoranda to terminate, errors in the "
         "commitment."],
        ['<font color="#B45309">Before Closing</font>',
         "Needed by closing day, but handled in the normal course.",
         "The deed, LLC documents, FinCEN details, HOA estoppel, affidavits, transfer forms, bring-down of an old "
         "commitment, taxes due or past due shown in Schedule B-II (paid at closing), a certified copy of a quiet "
         "title judgment entry."],
        ['<font color="#4D458A">Review / FYI</font>',
         "Standard exceptions that stay on the policy, and notes. Glance at them.",
         "Utility easements, plat restrictions, mineral rights, road rights of way, taxes not yet due."],
    ], [0.18, 0.37, 0.45])]
    s += [P("An item, opened", "h2"),
          P("Each item is a card: the headline, then exactly what to order, pay, sign or record. Click it to open the "
            "details."),
          shot("05-item-open", "An open item: why it matters, who provides it, the amount, and the exact wording "
                               "from the commitment.", 0.95)]
    s += [table(["Part", "Meaning"], [
        ["Provided by", "Who actually holds or provides it (seller, lender, county, court…)."],
        ["Owner", "Always the deal's TC, who chases it."],
        ["Source", "<b>B-I 4 · p.2</b> means Schedule B-I item 4 on page 2. <b>✓</b> the quoted wording was found "
                   "word for word on that page. <b>✗</b> it wasn't: open the commitment and check. No mark: a "
                   "scanned page or a checklist item, which can't be checked."],
        ["The quote", "The commitment's own words, so you rarely need to open the PDF."],
        ["New", "Added by an updated commitment (section 8)."],
    ], [0.2, 0.8])]

    # ---- 6
    s += section(6, "Working The List Every Day",
                 "The list is the team's live checklist. Keep it current and everyone (the Team Hub and the daily "
                 "email too) stays in step.")
    s += [steps([
        "<b>Tick the box</b> on the left when an item is done: it becomes <b>Cleared</b> and fades. Tick it again to "
        "reopen it.",
        "Click the <b>status</b> (OPEN, ORDERED…) to pick another one.",
        "Click the <b>date</b> to change when it's due.",
        "Open the item, type in <b>Notes</b> (e.g. \"Payoff requested from servicer 10/26\") and click "
        "<b>Save Notes</b>.",
    ]), shot("07-status-menu", "Changing a status. Every change saves at once and shows on everyone's screen.", 1.0,
             crop=(0.14, 0.22, 0.86, 0.66))]
    s += [table(["Status", "Use it when"], [
        ["Open", "Nothing has been done yet."],
        ["Ordered", "You've requested it (payoff letter ordered, estoppel requested, affidavit sent for signature)."],
        ["Received", "You have it, but title hasn't confirmed it's satisfied yet."],
        ["Cleared", "Done. Title confirmed, or it's recorded or paid."],
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
    s += [P("Weekends move back to the Friday before. A date shown in red is overdue. Admins can change these "
            "numbers in Settings.")]
    s += [box("Use the filters above the list: <b>Closing Blockers</b>, <b>Before Closing</b> or <b>Review / FYI</b> "
              "shows one group; <b>Open Only</b> hides what's done; <b>Expand All</b> opens every card. A good daily "
              "routine: open each deal, pick Open Only, work anything due in the next 3 days, update statuses.",
              "tip")]

    # ---- 7
    s += section(7, "When The Agent Misses Something",
                 "This is how the agent gets better. Report every miss, even small ones.")
    s += [steps([
        "On the deal, click <b>Report Missing Item</b>.",
        "Fill in <b>What's Missing</b>, <b>Where In The Document</b> (e.g. B-II #9, page 4) and <b>Why It Would "
        "Stop Or Delay The Closing</b>.",
        "Pick the <b>Priority</b> and <b>Who Has To Provide It</b>. Leave <b>Add it to this deal's list now</b> "
        "ticked so it goes straight onto your list (a Closing Blocker also goes to the Team Hub).",
        "Click <b>Send Feedback</b>. It lands in the Feedback Inbox on the Knowledge tab. Once an admin approves the "
        "lesson, the agent checks for it on every deal.",
    ]), shot("08-missing", "Report A Missing Item.", 0.62, crop=(0.305, 0.085, 0.705, 0.965), max_h=4.6)]
    s += [P("Something on the list is wrong or not needed?", "h2"),
          P("Open the item and click <b>Feedback</b> at the bottom right of the card: <b>Not Needed On This Deal</b> "
            "or <b>Wrong Information</b>. It goes to the Feedback Inbox. Then set the item to <b>Waived</b> with a "
            "note.")]

    # ---- 8
    s += section(8, "Updated Commitments And Re-Runs")
    s += [P("When the title company sends a revised commitment", "h2")]
    s += [steps([
        "On the deal, click <b>Updated Commitment</b>. Analyze opens with the deal already picked.",
        "Upload the new PDF, click <b>Read Documents</b>, check the details, then <b>Run Full Review</b>.",
        "Your statuses and notes carry over. New items are marked <b>New</b>; items the title company took off move "
        "to <b>Removed By The Title Company</b>, crossed out.",
    ])]
    s += [P("Re-run", "h2"),
          P("<b>Re-run</b> reads the latest commitment again with the latest team lessons, for example after an "
            "admin approves new lessons or you added a closing date. Statuses and notes are kept. It takes 1–3 "
            "minutes."),
          shot("10-rerun", "Re-run The Review.", 0.62, crop=(0.285, 0.37, 0.73, 0.625))]

    # ---- 9
    s += section(9, "Exporting The List",
                 "Send the checklist to the title company, the seller or the buyer, or keep a copy with the file.")
    s += [steps([
        "On the deal, click <b>Export List</b>.",
        "At the top, pick <b>Everything</b>, <b>No Review / FYI</b> or <b>Closing Blockers Only</b>. The number shows "
        "how many items each one has. A partial export says what was left out, and a blockers-only file is titled "
        "<b>Closing Blockers</b>.",
        "Click <b>PDF</b>, <b>Word</b>, <b>Excel</b> or <b>CSV</b>: the file downloads with the property address "
        "in its name.",
        "Or click <b>Google Sheets</b> or <b>Google Docs</b>: the file is created in the team's shared Google Drive "
        "folder and opens in a new tab. Everyone with access to that folder can see it.",
    ]), shot("09-export", "Export List, set to Closing Blockers Only.", 0.7, crop=(0.27, 0.26, 0.73, 0.74))]
    s += [box("Exports contain names, addresses and loan numbers. Send them only to people on the deal.", "warn")]

    # ---- 10
    s += section(10, "The Universal Team Hub Connection",
                 f"Every deal's Closing Blockers also live in the Universal Team Hub (hub.totalchb.com), so they sit "
                 f"with the rest of the team's work. You don't do anything to send them: the {APP} does it "
                 "for you, and keeps both sides in step.", need=4.5)
    s += [flow()]
    s += [P("What shows up in the hub", "h2")]
    s += bullets([
        "<b>One task per deal</b>, named <b>Title - </b><i>the property address</i>, in Monz's list and marked as "
        f"added by the {APP}.",
        "<b>One subtask per Closing Blocker</b>: the item's headline, a note with the action and where it comes from "
        "in the commitment (e.g. B-I 4), and the item's due date. The task links back to the deal here.",
        "<b>Only Closing Blockers.</b> Before Closing and Review / FYI items stay here. Exports, PDFs, amounts and "
        "notes are never sent.",
    ])
    s += [P("How it stays in step", "h2")]
    s += [table(["When…", "…this happens"], [
        ["A review or re-run finishes", "The deal's Closing Blockers go to the hub. The first time, the task is "
                                        "created."],
        ["You clear a blocker here (tick or status)", "It's ticked done in the hub."],
        ["Someone ticks a blocker done in the hub", "It turns <b>Cleared</b> here. Unticking it there makes it "
                                                    "<b>Open</b> here again."],
        ["You change a blocker's due date", "The subtask's date follows."],
        ["You Report a Missing Closing Blocker (added to the list)", "A new subtask appears."],
        ["An updated commitment removes a blocker", "It's no longer sent to the hub."],
        ["Anything was missed (the hub was busy, a connection dropped)", "A catch-up runs every 15 minutes for "
                                                                          "every open deal."],
    ], [0.42, 0.58])]
    s += [P("Changes normally show on the other side within moments, and always within about 15 minutes. Only "
            "the tick travels back from the hub: change titles, dates and notes here, where the list is worked.")]
    s += [P("Checking it's working", "h2"),
          P("At the bottom of every deal, under <b>Documents And Review History</b>, a <b>Team Hub</b> line shows when "
            "the Closing Blockers were last sent. If it says <b>Not reached yet</b>, nothing is lost: it tries again "
            "within 15 minutes. Admins also see a <b>Team Hub</b> tile in Settings → Connections."),
          shot("11-records", "The bottom of a deal: the documents, the Team Hub line and Mark Deal Closed.", 1.0,
               crop=(0.14, 0.64, 0.86, 0.86))]
    s += [box("Closing a deal here (Mark Deal Closed) stops sending it to the hub. Clear or waive its blockers "
              "first if you want the hub task to show as done.", "tip")]

    # ---- 11
    s += section(11, "Deals, Closing Out And The Daily Email")
    s += [P("The Deals page", "h2"),
          P("Every reviewed deal, newest first. Each card shows the deal type, closing date, TC and title company, "
            "the open Closing Blockers (or <b>No blockers</b>), the days to closing and how much of the list is done. "
            "Search by address, TC, title company or commitment number, and switch between <b>Open</b>, "
            "<b>Closed</b> and <b>All</b>. Click a card to open the deal.")]
    s += [P("Closing out a deal", "h2"),
          P("After it closes, scroll to the bottom of the deal and click <b>Mark Deal Closed</b>. It leaves the open "
            "list, the daily email and the Team Hub catch-up. <b>Reopen Deal</b> brings it back. The original PDFs "
            "stay under <b>Documents And Review History</b>; click one to open it.")]
    s += [P("The daily email", "h2"),
          P(f"Every weekday at 8:00 AM Eastern, everyone on the list gets one email from the <b>{APP}</b> "
            "(title-agent@totalchb.com) covering every open deal: its open Closing Blockers and anything due in the "
            "next 3 days, with overdue items flagged and a link straight to the deal. It's prepared in the early "
            "hours, so a status you change that morning shows up in the next day's email. With no open deals it "
            "still arrives and says so.")]

    # ---- 12
    s += section(12, "For The Owner And Admins",
                 "Admins approve what the agent learns and set up the team. Admins are listed in Settings; everyone "
                 "else can see Settings and Knowledge but not change them.")
    s += [P("Approving lessons (Knowledge tab)", "h2"),
          shot("16-knowledge", "Knowledge: how the agent scores, the active lessons, the checklist, and the Feedback "
                               "Inbox.", 1.0, crop=(0.14, 0.12, 0.86, 1.0), max_h=4.4)]
    s += [steps([
        "Open <b>KNOWLEDGE</b>. <b>Feedback Waiting</b> shows how many items need an admin.",
        "Read each card in the <b>Feedback Inbox</b> (Missing Item, Not Needed, Wrong Info or Training Gap). The "
        "suggested lesson is in the text box.",
        "Edit it into a <b>general rule</b> the agent can apply to every commitment. Good: \"When a city lists unpaid "
        "water or sewer charges, order a final read and list the payoff as a Closing Blocker.\" Bad: names, "
        "addresses, amounts or case numbers from one deal.",
        "Click <b>Approve Lesson</b> (it applies from the next review) or <b>Reject</b>.",
    ])]
    s += [P("Under <b>Lessons</b>, every lesson has an on/off switch: turn one off if it causes wrong items. Add your "
            "own in the box below the list with <b>Add Lesson</b>. The first lessons came from the 8 worked "
            "commitments the team provided. Further down: the training examples with their latest score, and "
            "<b>The Professional Checklist</b> (34 checks the agent runs on every deal)."),
          shot("17-lessons", "Lessons: each one can be turned off and on.", 1.0, crop=(0.14, 0.56, 0.86, 1.0))]
    s += [CondPageBreak(3.6 * inch), P("Settings", "h2"),
          P("Click your initials → <b>Settings</b>. Change what you need, then click <b>Save Settings</b>.")]
    s += [table(["Setting", "What to put"], [
        ["Admins", "Emails of the people who approve lessons and change settings, one per line. With nobody listed, "
                   "everyone is an admin, so keep at least one."],
        ["TCs", "Names of the TCs, one per line. You pick from this list when confirming a deal."],
        ["Daily Email: Send To", "Everyone who gets the morning summary, one per line."],
        ["Daily Email: Send From", "title-agent@totalchb.com (leave as is)."],
        ["Due Dates", "Days before closing for each kind of item (payoffs 10, curative 14, documents 5, bring-down 5, "
                      "closing 0)."],
        ["Google Drive Folder", "The link of the shared folder for Google Sheets / Docs exports. After changing it, "
                                "Save, then click <b>Test Google Folder</b>. The setup steps are under it."],
    ], [0.27, 0.73])]
    s += [P("Connections", "h2"),
          P("The tiles at the bottom of Settings show whether everything the app depends on is working. They're set "
            "in the engine's secrets (GitHub), never on this page."),
          shot("19-connections", "The Connections tiles.", 1.0, crop=(0.14, 0.56, 0.86, 0.9))]
    s += [table(["Tile", "What it tells you"], [
        ["AI (Anthropic)", "<b>Connected</b>: reviews can run."],
        ["Database", "<b>Firestore</b>: the deals live in the company's own Firebase project."],
        ["Google", "<b>Set Up</b>: Google Sheets / Docs exports work (saved by the export script)."],
        ["Team Hub", "<b>Connected</b>: Closing Blockers go to hub.totalchb.com and ticks come back."],
        ["Daily Email", "<b>Scheduled</b>: this morning's email is queued for 8:00. <b>Sending</b>: it went out (with "
                        "the time and how many people). <b>Skipped</b> or <b>Failed</b>: the reason is shown; the next "
                        "weekday tries again."],
    ], [0.22, 0.78])]
    s += [box("Access is the company Google account: when someone leaves and their @totalchb.com account is "
              "closed, they can no longer sign in. Remove them from Admins and TCs too.", "warn")]
    s += [P("Training (optional)", "h2"),
          P("To measure the agent, open <b>TRAINING</b>, upload a commitment your team already worked, pick the deal "
            "type, paste the closer's list as is and click <b>Compare With Agent</b>. You'll see what both found, "
            "what the agent missed (each becomes a suggested lesson in the Feedback Inbox) and what it added. Leave "
            "the list empty for a clean title: the agent should then find no Closing Blockers. Each comparison is a "
            "full review: 1–3 minutes and roughly $1–2 in AI usage."),
          shot("15-training-results", "Training: the closer's list compared with the agent's.", 1.0,
               crop=(0.14, 0.57, 0.86, 0.93))]

    # ---- 13
    s += section(13, "Good Habits")
    s += bullets([
        "<b>Run every commitment through the agent</b> the day it arrives, and every revised commitment too.",
        "<b>Always add the closing date.</b> Without it, there are no due dates and no countdown.",
        "<b>Check Coverage.</b> Anything short of 100% or a red box means: read those items yourself.",
        "<b>Check every ✗</b> next to a source against the commitment.",
        "<b>Keep statuses current.</b> The Team Hub, the daily email and the whole team rely on them.",
        "<b>Report every miss.</b> One report can save every future deal.",
        "<b>Keep deal data inside the company.</b> Don't forward exports outside the people on the deal.",
        "<b>A person signs off</b> on the list before closing. The agent helps; it doesn't decide.",
    ])

    # ---- 14
    s += section(14, "Quick Answers")
    s += [table(["Question", "Answer"], [
        ["It says my account doesn't have access.", "Sign in with your @totalchb.com Google account, not a personal "
                                                    "one."],
        ["Does it work on my phone?", "Yes, in the phone's browser with the same link and sign-in."],
        ["\"The AI service is busy\" or another error.", "Wait a minute and click the button again. Nothing is lost."],
        ["\"Couldn't reach the Title Commitment Agent.\"", "Your internet connection dropped. Try again once it's "
                                                           "back."],
        ["The numbering check is red.", "Read the listed item numbers in the commitment yourself and add anything "
                                        "missing with Report Missing Item."],
        ["An item is wrong.", "Open it → Feedback → Wrong Information, then set it to Waived with a note."],
        ["I picked the wrong deal type or date.", "Deal → Updated Commitment, upload the same PDF and fix the details "
                                                  "on the confirm screen."],
        ["Can I upload a scanned PDF?", "Yes. Quotes from scanned pages have no ✓, because there's no text to check "
                                        "them against."],
        ["A blocker isn't in the Team Hub yet.", "Look at the Team Hub line at the bottom of the deal. It catches up "
                                                 "within 15 minutes; if it still says Not reached yet, tell an admin."],
        ["I ticked a subtask in the hub. Will it clear here?", "Yes, the blocker turns Cleared here, usually within "
                                                               "moments."],
        ["Where are the original PDFs?", "Bottom of the deal → Documents And Review History."],
        ["The daily email didn't arrive.", "Check spam once and mark it Not Spam. Then an admin checks Settings → "
                                           "Connections → Daily Email, which shows what happened."],
        ["Google Sheets / Docs shows an error.", "The message says what's wrong. Use Excel or Word for now and tell an "
                                                 "admin (Settings → Test Google Folder)."],
        ["Who sees my changes?", "Everyone on the team, immediately. Your email is recorded on each change."],
    ], [0.38, 0.62])]

    # ---- reference card
    s += [PageBreak(), P("Quick Reference Card", "h1"), P("Print this page and keep it at your desk.", "lead")]
    ref = [
        ("New commitment", "ANALYZE → drop the PDF (+ contract) → Read Documents → confirm deal type and closing "
                           "date → Run Full Review."),
        ("Revised commitment", "Deal → Updated Commitment → upload → Read Documents → Run Full Review."),
        ("Every morning", "Read the daily email → open each deal → Open Only → work what's due → update statuses "
                          "and notes."),
        ("Item done", "Tick its box (Cleared). In the Team Hub it's ticked done too."),
        ("Something's missing", "Deal → Report Missing Item → fill it in → Send Feedback."),
        ("Something's wrong", "Open the item → Feedback → Wrong Information / Not Needed → set it to Waived."),
        ("Send the list", "Deal → Export List → Everything / No Review / FYI / Closing Blockers Only → PDF, Word, "
                          "Excel, CSV, Google Sheets or Docs."),
        ("Deal closed", "Bottom of the deal → Mark Deal Closed."),
    ]
    s.append(table(["I want to…", "Do this"], [[a, b] for a, b in ref], [0.25, 0.75]))
    pri = Table([[Para('<font name="Nunito-Bold" color="#BD2239">Closing Blocker</font><br/>Stops the closing. '
                       'Payoffs, liens, judgments, court items. Also in the Team Hub.', S["cell"]),
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
    marks = Table([[Para(f'<font name="Nunito-Bold">{a}</font><br/>{b}', S["cell"]) for a, b in (
        ("Source marks", "<b>✓</b> quote found on the page · <b>✗</b> check it yourself · no mark: scanned page or "
                         "checklist item"),
        ("Due dates", "Payoffs 10 days before closing · court / curative 14 · documents 5 · bring-down 5 · paid at "
                      "the table: closing day · weekends move to Friday"),
        ("Team Hub", "Closing Blockers only · one task per deal (Title - address) · ticks travel both ways · "
                     "catch-up every 15 minutes"))]], colWidths=[WIDTH / 3] * 3)
    marks.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), LAV), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                               ("LINEAFTER", (0, 0), (1, 0), 4, colors.white), ("TOPPADDING", (0, 0), (-1, -1), 8),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 8), ("LEFTPADDING", (0, 0), (-1, -1), 9),
                               ("ROUNDEDCORNERS", [8, 8, 8, 8])]))
    s += [st, Spacer(1, 10), marks]
    return s


def build() -> Path:
    doc = BaseDocTemplate(str(OUT), pagesize=letter, title=f"{APP} User Guide",
                          author="Total Cash Home Buyers", subject=f"How to use the {APP}")
    cover_frame = Frame(MARGIN, MARGIN, WIDTH, PAGE_H - 2 * MARGIN, id="cover")
    body = Frame(MARGIN, 0.8 * inch, WIDTH, PAGE_H - 1.75 * inch, id="body")
    doc.addPageTemplates([PageTemplate("cover", [cover_frame], onPage=cover),
                          PageTemplate("inner", [body], onPage=inner)])
    doc.build([Spacer(1, 1), *story()])
    return OUT


if __name__ == "__main__":
    print(build())
