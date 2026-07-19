from pathlib import Path


def test_airport_feature_image_has_reduced_width():
    css = Path("app/static/css/information.css").read_text(
        encoding="utf-8"
    )
    block = css.split("/* TRAVEL FEATURE IMAGE SIZE V2 */", 1)[1]

    assert ".travel-image-feature {" in block
    assert "width: min(100%, 980px);" in block
    assert "aspect-ratio: 16 / 6.8;" in block
    assert "margin: 0 auto 22px;" in block


def test_airport_feature_image_remains_responsive():
    css = Path("app/static/css/information.css").read_text(
        encoding="utf-8"
    )
    block = css.split("/* TRAVEL FEATURE IMAGE SIZE V2 */", 1)[1]

    assert "@media (max-width: 1100px)" in block
    assert "@media (max-width: 700px)" in block
    assert "aspect-ratio: 16 / 9.2;" in block
