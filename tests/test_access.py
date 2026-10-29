from titleagent.access import email_allowed

DOMAINS = ("totalchb.com",)


def test_company_domain_and_listed_emails_get_in():
    assert email_allowed("tc@totalchb.com", (), DOMAINS)
    assert email_allowed("  TC@TotalCHB.com ", (), DOMAINS)
    assert email_allowed("owner@example.org", ("owner@example.org",), DOMAINS)


def test_everyone_else_is_kept_out():
    assert not email_allowed("someone@gmail.com", (), DOMAINS)
    assert not email_allowed("x@evil-totalchb.com", (), DOMAINS)
    assert not email_allowed("x@totalchb.com.evil.io", (), DOMAINS)
    assert not email_allowed("", (), DOMAINS) and not email_allowed(None, (), DOMAINS)
    assert not email_allowed("no-at-sign", (), DOMAINS)
