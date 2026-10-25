from datetime import date

from titleagent.compare import carry_over
from titleagent.duedates import due_date
from titleagent.emailer import summary_html
from titleagent.grounding import found_on, verify
from titleagent.models import ActionItem, Source
from titleagent.pdf import PdfText
from titleagent.training import parse_expert_list


def item(title, quote="", status="Open", key="", origin="commitment", priority="blocker", due=None):
    return ActionItem(key=key, priority=priority, category="Other", title=title, action="do it",
                      provided_by="Seller", sources=[Source(ref="B-I 1", page=1, quote=quote)], status=status,
                      origin=origin, due_date=due)


def test_due_dates_move_off_weekends():
    closing = date(2026, 11, 16)  # Monday
    assert due_date(closing, "payoff") == date(2026, 11, 6)
    assert due_date(closing, "closing") == date(2026, 11, 16)
    assert due_date(date(2026, 11, 22), "closing") == date(2026, 11, 20)  # Sunday -> Friday
    assert due_date(closing, "none") is None and due_date(None, "payoff") is None


def test_quotes_are_checked_against_the_page():
    page = "8.Release of Tax Lien Certificate against Jane Q. Example, in the original\namount of $1,234.56"
    assert found_on("Release of Tax Lien Certificate against Jane Q. Example, in the original amount", page)
    assert not found_on("Satisfaction of mortgage to First Example Bank", page)
    text = PdfText(pages=[page * 5, "short"], sha256="")
    assert verify(Source(ref="B-I 8", page=1, quote="amount of $1,234.56"), text).verified is True
    assert verify(Source(ref="B-I 8", page=2, quote="anything"), text).verified is None  # scanned / no text
    assert verify(Source(ref="Checklist: x", page=None, quote=""), text).verified is None


def test_updated_commitment_marks_new_and_removed():
    prev = [item("Open mortgage to First Example Bank", "release of Mortgage to First Example Bank", "Ordered",
                 key="m1"),
            item("Judgment Demo Collections", "Judgment in favor of Demo Collections", key="j1"),
            item("Added by a person", key="fb1", origin="feedback")]
    new = [item("Open mortgage to First Example Bank", "release of Mortgage to First Example Bank"),
           item("HOA estoppel", "Declaration of Covenants")]
    out = {i.title: i for i in carry_over(new, prev, mark_changes=True)}
    assert out["Open mortgage to First Example Bank"].key == "m1"
    assert out["Open mortgage to First Example Bank"].status == "Ordered"
    assert out["HOA estoppel"].change == "new"
    assert out["Judgment Demo Collections"].change == "removed"
    assert out["Added by a person"].change == ""


def test_closer_lists_pasted_from_email():
    text = """3. Secure and record a Satisfaction of that certain mortgage dated May 1, 2026,
in the original principal amount of $100,000.00.

7. Payment and Release of Prior Owner Judgment 99 XX 00001, in the amount of $100.00.
8. Payment and Release of Prior Owner Judgment 99 XX 00002, in the amount of $200.00."""
    items = parse_expert_list(text)
    assert len(items) == 3
    assert items[0].startswith("3. Secure and record") and items[0].endswith("$100,000.00.")


def test_daily_email_lists_blockers_and_due_items():
    deals = [{"id": 1, "address": "1 Sample St", "deal_type": "Wholesale (Assignment)", "closing_date": None,
              "tc": "Pat"}]
    items = {1: [item("Mortgage payoff"), item("Deed", priority="before", due="2026-10-26"),
                 item("Cleared lien", status="Cleared"), item("Later doc", priority="before", due="2026-12-01")]}
    subject, html = summary_html(deals, items, date(2026, 10, 25))
    assert "1 open blocker," in subject and "1 due soon" in subject
    assert "Mortgage payoff" in html and "Deed" in html
    assert "Cleared lien" not in html and "Later doc" not in html
