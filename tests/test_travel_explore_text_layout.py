from pathlib import Path


def test_explore_labels_stack_above_titles():
    css = Path("app/static/css/information.css").read_text(
        encoding="utf-8"
    )
    block = css.split("/* TRAVEL EXPLORE TEXT LAYOUT V2 */", 1)[1]

    assert ".travel-list-explore .travel-item {" in block
    assert "grid-template-columns: minmax(0, 1fr);" in block
    assert ".travel-list-explore .travel-item-number {" in block
    assert "white-space: normal;" in block


def test_explore_layout_has_mobile_spacing():
    css = Path("app/static/css/information.css").read_text(
        encoding="utf-8"
    )
    block = css.split("/* TRAVEL EXPLORE TEXT LAYOUT V2 */", 1)[1]

    assert "@media (max-width: 700px)" in block
    assert "padding-top: 17px;" in block
    assert "padding-bottom: 17px;" in block
