from titleagent.access import email_allowed, password_ok

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


def test_password():
    assert password_ok("s3cret", "s3cret")
    assert not password_ok("wrong", "s3cret")
    assert not password_ok("", None) and not password_ok("anything", "")


def test_remembered_sign_in_pass():
    from titleagent.access import make_pass, read_pass

    now = 1_800_000_000
    token = make_pass("tc@totalchb.com", "s3cret", now)
    assert read_pass(token, "s3cret", now + 86400) == "tc@totalchb.com"
    assert read_pass(token, "s3cret", now + 31 * 86400) is None  # expired after 30 days
    assert read_pass(token, "new-password", now) is None  # changing the password signs everyone out
    email_b64, expiry, sig = token.split(".")
    assert read_pass(f"{email_b64}.{int(expiry) + 999999}.{sig}", "s3cret", now) is None  # tampered expiry
    assert read_pass("garbage", "s3cret", now) is None and read_pass(None, "s3cret", now) is None
    assert read_pass(token, None, now) is None
