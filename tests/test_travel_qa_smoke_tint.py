from pathlib import Path


def test_travel_and_qa_cards_use_local_smoke_tint():
    css = Path("app/static/css/information.css").read_text(
        encoding="utf-8"
    )
    block = css.split("/* TRAVEL QA SMOKE TINT V3 */", 1)[1]

    assert ".travel-story {" in block
    assert ".qa-grid {" in block
    assert "rgba(0, 0, 0, .30)" in block
    assert "brightness(.94)" in block


def test_smoke_tint_does_not_restore_page_wide_film():
    css = Path("app/static/css/information.css").read_text(
        encoding="utf-8"
    )
    block = css.split("/* TRAVEL QA SMOKE TINT V3 */", 1)[1]

    assert "ambient-slideshow-shade" not in block
    assert 'body[data-active-tab="travel"]' not in block
    assert 'body[data-active-tab="qa"]' not in block


def test_qa_items_keep_readable_nested_tint():
    css = Path("app/static/css/information.css").read_text(
        encoding="utf-8"
    )
    block = css.split("/* TRAVEL QA SMOKE TINT V3 */", 1)[1]

    assert ".qa-item {" in block
    assert ".qa-item[open] {" in block
    assert ".qa-answer p" in block
