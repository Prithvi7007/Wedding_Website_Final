from pathlib import Path


def test_private_invitation_uses_restored_clear_glass_theme():
    template = Path("app/templates/invitation/open.html").read_text(
        encoding="utf-8"
    )
    css = Path("app/static/css/invitation-open.css").read_text(
        encoding="utf-8"
    )

    assert 'class="invitation-render-v2"' in template
    assert "css/invitation-open.css" in template
    assert "js/invitation-open.js" in template
    assert "open-invitation-form" in template
    assert "backdrop-filter" in css
    assert "RESTORED CLEAR OPTICAL GLASS" in css
    assert "DSC06717-1170.webp" in css
