from titleagent import demo
from titleagent.models import EntryOut
from titleagent.numbering import check, missing_numbers, printed_numbers
from titleagent.pdf import PdfText, read_pdf


def entries(*numbers):
    return [EntryOut(number=str(n), page=1, text="x") for n in numbers]


def test_sample_commitment_numbers_are_found():
    found = printed_numbers(read_pdf(demo.sample_commitment_pdf()))
    assert found == {"B-I": set(range(1, 10)), "B-II": set(range(1, 9))}


def test_layouts_seen_in_real_commitments():
    # pypdf drops the space after the number; a number can be followed by a digit; "Schedule A hereof" inside an
    # exception must not end the section; footers that mention "Schedule B, Part I" are not headings
    page = "\n".join([
        "This Commitment is not valid without Schedule A; Schedule B, Part I—Requirements; and Schedule B, Part II.",
        "SCHEDULE B  I",
        "REQUIREMENTS",
        "1.The Proposed Insured must notify the Company",
        "2.Pay the agreed amount",
        "5.FOR 24 MONTH CHAIN OF TITLE:",
        "1. Being the same property conveyed to someone",
        "SCHEDULE B, PART II",
        "Exceptions",
        "6.2025 County Taxes were SOLD to a private party",
        "7. Pursuant to law, leases recorded subsequent to the Date of Policy",
        "Schedule A hereof. (As to Loan Policy only).",
        "8. Notwithstanding the reference to acreage",
        "EXHIBIT A",
        "9. Not an exception (legal description numbering)",
    ])
    found = printed_numbers(PdfText(pages=[page], sha256=""))
    assert found["B-I"] == {1, 2, 5}
    assert found["B-II"] == {6, 7, 8}


def test_missing_numbers_holes_and_cut_short_lists():
    assert missing_numbers(entries(1, 2, 4), {1, 2, 3, 4}) == [3]
    assert missing_numbers(entries(1, 2, 3), {1, 2, 3, 4, 5}) == [4, 5]  # list cut short
    assert missing_numbers(entries(1, 2, 3), {1, 2, 3, 40}) == []  # far-off number is other content
    assert missing_numbers([], {1, 2}) == [1, 2]
    assert missing_numbers(entries("1(4)", "2", "3"), set()) == []


def test_scanned_document_relies_on_the_sequence():
    gaps = check(None, entries(1, 2, 5), entries(1, 2, 3))
    assert gaps == {"B-I": [3, 4], "B-II": []}
