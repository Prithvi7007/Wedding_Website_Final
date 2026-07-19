from pathlib import Path


def test_private_invitation_contains_family_invitation_copy():
    template = Path("app/templates/invitation/open.html").read_text(
        encoding="utf-8"
    )

    expected_text = (
        "Peter &amp; Shefali Lawrence",
        "Mohan &amp; Sunitha Kokku",
        "invite you to celebrate the wedding of their children",
        "Adlin <span aria-hidden=\"true\">&amp;</span> Prithvi",
        "Doesn’t look like your invitation? Please contact Adlin or Prithvi.",
    )

    for text in expected_text:
        assert text in template


def test_private_invitation_keeps_personalized_guest_name():
    template = Path("app/templates/invitation/open.html").read_text(
        encoding="utf-8"
    )

    assert "Welcome, {{ guest_name }}" in template
    assert "invitation.display_name" in template

