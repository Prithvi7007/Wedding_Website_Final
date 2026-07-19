from pathlib import Path


def test_dashboard_uses_shared_optical_glass_tokens():
    css = Path("app/static/css/tokens.css").read_text(encoding="utf-8")
    assert "OPTICAL GLASS SYSTEM V1" in css
    assert "--glass-clear:" in css
    assert "--glass-readable:" in css
    assert "--glass-filter:" in css


def test_major_tabs_use_optical_glass_family():
    files = {
        "app/static/css/shell.css": "DASHBOARD OPTICAL GLASS V1",
        "app/static/css/welcome.css": "WELCOME OPTICAL GLASS V1",
        "app/static/css/schedule.css": "SCHEDULE OPTICAL GLASS V1",
        "app/static/css/information.css": "INFORMATION OPTICAL GLASS V1",
    }
    for filename, marker in files.items():
        assert marker in Path(filename).read_text(encoding="utf-8")


def test_qa_rows_do_not_each_use_backdrop_filter():
    css = Path("app/static/css/information.css").read_text(encoding="utf-8")
    refresh = css.split("/* INFORMATION OPTICAL GLASS V1 */", 1)[1]
    qa_block = refresh.split(".qa-item {", 1)[1].split("}", 1)[0]
    assert "backdrop-filter" not in qa_block


def test_glass_system_has_non_blur_fallback():
    css = Path("app/static/css/information.css").read_text(encoding="utf-8")
    assert "@supports not" in css
    assert "backdrop-filter: blur(1px)" in css
