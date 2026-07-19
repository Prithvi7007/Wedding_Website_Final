from pathlib import Path


def test_welcome_uses_soft_scrim_instead_of_boxed_glass():
    css = Path("app/static/css/welcome.css").read_text(encoding="utf-8")
    block = css.split("/* WELCOME SOFT SCRIM V2 */", 1)[1]

    assert "border: 0;" in block
    assert "box-shadow: none;" in block
    assert "mask-image: radial-gradient" in block
    assert ".welcome-copy::after" in block
    assert "display: none;" in block


def test_welcome_controls_keep_glass_treatment():
    css = Path("app/static/css/welcome.css").read_text(encoding="utf-8")

    assert ".welcome-schedule-button" in css
    assert ".countdown-inline > div::before" in css
    assert "backdrop-filter" in css
