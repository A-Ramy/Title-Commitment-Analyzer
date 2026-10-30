from datetime import UTC, date, datetime

from titleagent.compare import carry_over
from titleagent.config import _decode_service_account
from titleagent.duedates import due_date
from titleagent.emailer import EASTERN, already_done, plan, run_record, run_status, send, summary_html
from titleagent.exports.google import check_folder, folder_id_from
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


def test_folder_id_from_links_and_bare_ids():
    assert folder_id_from("https://drive.google.com/drive/folders/0AbC-d_12?usp=sharing") == "0AbC-d_12"
    assert folder_id_from("https://drive.google.com/drive/u/1/folders/1xYz") == "1xYz"
    assert folder_id_from("https://drive.google.com/open?id=1xYz&authuser=0") == "1xYz"
    assert folder_id_from("  1xYz ") == "1xYz"
    assert folder_id_from("") == ""


class FakeDrive:
    def __init__(self, meta):
        self.meta = meta

    def files(self):
        return self

    def get(self, **_):
        return self

    def execute(self):
        return self.meta


def test_check_folder_needs_a_shared_drive_folder_it_can_write(monkeypatch):
    from titleagent.exports import google

    sa = {"client_email": "agent@proj.iam.gserviceaccount.com"}
    folder = {"name": "Title Checklists", "mimeType": "application/vnd.google-apps.folder"}
    cases = [({**folder, "driveId": "0A", "capabilities": {"canAddChildren": True}}, True, "Title Checklists"),
             ({**folder, "capabilities": {"canAddChildren": True}}, False, "My Drive"),
             ({**folder, "driveId": "0A", "capabilities": {"canAddChildren": False}}, False, "Content Manager"),
             ({"name": "x.pdf", "mimeType": "application/pdf", "driveId": "0A"}, False, "not a folder")]
    for meta, ok, words in cases:
        monkeypatch.setattr(google, "_drive", lambda _sa, m=meta: FakeDrive(m))
        got_ok, msg = check_folder(sa, "https://drive.google.com/drive/folders/0AbC")
        assert got_ok is ok and words in msg
    assert check_folder(sa, "")[0] is False


def test_service_account_pasted_as_json():
    assert _decode_service_account(None, '{"client_email": "a@b.iam.gserviceaccount.com"}') == {
        "client_email": "a@b.iam.gserviceaccount.com"}
    assert _decode_service_account(None, None) is None


def test_daily_email_status_for_settings():
    assert run_status(None)[0] == "No Run Yet"
    sent = run_record("sent", "3 recipients", datetime(2026, 10, 27, 16, 50, tzinfo=UTC))
    value, sub, cls = run_status(sent)
    assert (value, cls) == ("Sending", "up") and "Oct 27, 12:50 PM ET" in sub and "3 recipients" in sub
    assert run_status(run_record("failed", "Email service returned 403", datetime.now(UTC)))[2] == "down"


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def json(self):
        if isinstance(self.body, str):
            raise ValueError("not JSON")
        return self.body


def test_google_export_through_the_apps_script(monkeypatch):
    import requests

    from titleagent.config import Secrets
    from titleagent.exports import google

    secrets = Secrets(None, None, None, google_export_url="https://script.google.com/macros/s/x/exec",
                      google_export_key="k1")
    assert secrets.has_google
    sent = []

    def post(url, json, timeout):
        sent.append(json)
        if json["key"] != "k1":
            return FakeResponse({"ok": False, "error": "wrong key"})
        if json["action"] == "ping":
            return FakeResponse({"ok": True, "folder": "Title Checklists"})
        return FakeResponse({"ok": True, "link": "https://docs.google.com/spreadsheets/d/abc"})

    monkeypatch.setattr(requests, "post", post)
    link = google.export(secrets, "https://drive.google.com/drive/folders/1Fold?usp=sharing", "Deal", b"xlsx", "sheet")
    assert link.endswith("/abc")
    assert sent[-1]["folder"] == "1Fold" and sent[-1]["kind"] == "sheet" and sent[-1]["data"] == "eGxzeA=="
    assert google.check(secrets, "1Fold") == (True, "Connected: exports go to “Title Checklists”.")

    wrong = Secrets(None, None, None, google_export_url=secrets.google_export_url, google_export_key="nope")
    ok, msg = google.check(wrong, "1Fold")
    assert not ok and "key doesn't match" in msg

    monkeypatch.setattr(requests, "post", lambda *a, **k: FakeResponse("<html>Sign in</html>"))
    ok, msg = google.check(secrets, "1Fold")
    assert not ok and "Anyone" in msg
    assert "Drive service" in google._script_error("ReferenceError: Drive is not defined")
    assert google.check(Secrets(None, None, None), "1Fold")[0] is False


def test_daily_email_goes_out_at_8_eastern():
    utc = lambda *a: datetime(*a, tzinfo=UTC)  # noqa: E731
    action, at = plan(utc(2026, 10, 28, 6, 17))  # Wed 2:17 AM EDT
    assert action == "schedule" and at.astimezone(EASTERN).strftime("%Y-%m-%d %H:%M %Z") == "2026-10-28 08:00 EDT"
    action, at = plan(utc(2026, 11, 4, 12, 17))  # Wed 7:17 AM EST (after the clock change)
    assert action == "schedule" and at.astimezone(UTC).hour == 13
    assert plan(utc(2026, 10, 28, 16, 50)) == ("now", None)  # a run hours late sends right away
    assert plan(utc(2026, 10, 31, 10, 47)) == ("skip", None)  # Saturday


def test_only_one_email_a_day():
    day = date(2026, 10, 28)
    at = datetime(2026, 10, 28, 12, 0, tzinfo=UTC)
    scheduled = run_record("scheduled", "3 recipients", at, day, datetime(2026, 10, 28, 12, 0, tzinfo=UTC))
    assert already_done(scheduled, day) and not already_done(scheduled, date(2026, 10, 29))
    assert not already_done(run_record("failed", "503", at, day), day)  # a failed try is tried again
    assert not already_done(run_record("test", "3 recipients", at, day), day)  # a manual test isn't the 8:00 email
    assert not already_done(None, day)
    value, sub, _ = run_status(scheduled, now=datetime(2026, 10, 28, 7, 0, tzinfo=EASTERN))
    assert value == "Scheduled" and "goes out Oct 28, 8:00 AM ET" in sub
    value, sub, _ = run_status(scheduled, now=datetime(2026, 10, 28, 9, 0, tzinfo=EASTERN))
    assert value == "Sending" and "last sent Oct 28, 8:00 AM ET" in sub


def test_send_hands_resend_the_delivery_time(monkeypatch):
    import requests

    bodies = []

    class Ok:
        status_code = 200
        text = ""

    monkeypatch.setattr(requests, "post", lambda url, headers, timeout, json: bodies.append(json) or Ok())
    at = datetime(2026, 10, 29, 8, 0, tzinfo=EASTERN)
    send("re_x", "title-agent@totalchb.com", ["a@totalchb.com"], "s", "<p>h</p>", at)
    send("re_x", "title-agent@totalchb.com", ["a@totalchb.com"], "s", "<p>h</p>")
    assert bodies[0]["scheduled_at"] == "2026-10-29T08:00:00-04:00" and "scheduled_at" not in bodies[1]


def test_daily_email_is_branded_and_lists_every_open_deal():
    deals = [{"id": 7, "address": "1 Sample St", "deal_type": "Double Close", "closing_date": "2026-11-20",
              "tc": "Pat"}, {"id": 8, "address": "2 Example Ave", "deal_type": "Fix & Flip", "closing_date": None,
                             "tc": "Sam"}]
    items = {7: [item("Payoff", key="a", due="2026-10-20")], 8: []}
    _, html = summary_html(deals, items, date(2026, 10, 25), "https://title.totalchb.com")
    assert 'src="https://title.totalchb.com/logo-full.png"' in html and "Title Commitment" in html
    assert "1 open Closing Blocker across 2 open deals" in html  # the inbox preview line
    assert "Overdue · Oct 20" in html and "On Track" in html and "2 Example Ave" in html
    _, quiet = summary_html(deals[1:], {8: []}, date(2026, 10, 25), "https://title.totalchb.com")
    assert "nothing due in the next 3 days" in quiet and "2 Example Ave" in quiet


def test_email_links_open_the_deal():
    deals = [{"id": 7, "address": "1 Sample St", "deal_type": "Double Close", "closing_date": None, "tc": "Pat"}]
    _, html = summary_html(deals, {7: [item("Payoff", key="a")]}, date(2026, 10, 25), "https://title.totalchb.com/")
    assert 'href="https://title.totalchb.com/#/deal/7"' in html
