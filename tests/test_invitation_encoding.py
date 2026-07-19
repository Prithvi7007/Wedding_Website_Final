from pathlib import Path


def test_invitation_ornaments_use_html_entities():
    template = Path("app/templates/invitation/open.html").read_text(
        encoding="utf-8"
    )

    assert "âœ" not in template
    assert "✦" not in template
    assert template.count("&#10022;") >= 4
