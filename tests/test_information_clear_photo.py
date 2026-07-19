from pathlib import Path


def test_information_tabs_remove_heavy_page_film():
    css = Path("app/static/css/information.css").read_text(
        encoding="utf-8"
    )
    block = css.split("/* INFORMATION CLEAR PHOTO V2 */", 1)[1]

    assert 'body[data-active-tab="travel"] .ambient-slideshow-shade' in block
    assert 'body[data-active-tab="registry"] .ambient-slideshow-shade' in block
    assert 'body[data-active-tab="qa"] .ambient-slideshow-shade' in block

    assert "rgba(18, 14, 11, .88)" not in block
    assert "rgba(17, 13, 11, .84)" not in block


def test_travel_registry_and_qa_use_clearer_materials():
    css = Path("app/static/css/information.css").read_text(
        encoding="utf-8"
    )
    block = css.split("/* INFORMATION CLEAR PHOTO V2 */", 1)[1]

    assert ".travel-story {" in block
    assert ".registry-copy::before {" in block
    assert ".registry-keepsake {" in block
    assert ".qa-grid {" in block
    assert "brightness(1.02)" in block


def test_registry_copy_uses_feathered_scrim_not_box():
    css = Path("app/static/css/information.css").read_text(
        encoding="utf-8"
    )
    block = css.split("/* INFORMATION CLEAR PHOTO V2 */", 1)[1]
    registry = block.split(".registry-copy::before {", 1)[1].split("}", 1)[0]

    assert "border: 0;" in registry
    assert "box-shadow: none;" in registry
    assert "mask-image: radial-gradient" in registry
