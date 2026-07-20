from pathlib import Path


def test_updated_qa_answers_are_present():
    template = Path("app/templates/tabs/qa.html").read_text(
        encoding="utf-8"
    )

    expected = [
        "Please refer to the dress code and inspiration attached in the Schedule section.",
        "That limit is unique to your private invitation link.",
        "Please do not include children under age 8",
        "arriving 15–20 minutes before",
        "Yes, parking is available at each venue.",
        "The Travel tab includes airports, recommended stay areas, local activities,",
        "Peter Lawrence (570-309-5575)",
        "Mohan (+91 93931-47047)",
    ]

    for text in expected:
        assert text in template


def test_old_qa_answers_are_removed():
    template = Path("app/templates/tabs/qa.html").read_text(
        encoding="utf-8"
    )

    removed = [
        "Festive yellow shades are encouraged for Haldi",
        "arriving 20–30 minutes before",
        "Parking varies by venue.",
        "The hotel booking link will be added when finalized.",
        "reach out to Adlin or Prithvi directly.",
    ]

    for text in removed:
        assert text not in template


def test_contact_numbers_are_clickable():
    template = Path("app/templates/tabs/qa.html").read_text(
        encoding="utf-8"
    )
    css = Path("app/static/css/information.css").read_text(
        encoding="utf-8"
    )

    expected_links = [
        'href="tel:+18138257545"',
        'href="tel:+18137239399"',
        'href="tel:+15703095575"',
        'href="tel:+919393147047"',
    ]

    for link in expected_links:
        assert link in template

    assert "Q&A UPDATED ANSWERS V1" in css
    assert ".qa-contact-link {" in css
