from pathlib import Path


def test_slideshow_uses_exactly_two_buffers():
    template = Path("app/templates/components/slideshow.html").read_text(encoding="utf-8")
    assert template.count("data-slide-buffer=") == 2


def test_dashboard_has_fragment_navigation():
    template = Path("app/templates/dashboard/shell.html").read_text(encoding="utf-8")
    assert "data-fragment-url" in template
    assert 'id="tab-content"' in template


def test_responsive_slideshow_assets_exist():
    asset_dir = Path("app/static/images/slideshow")
    for name in ("DSC06660", "DSC06692", "DSC06717", "DSC06785", "DSC06855", "DSC06882"):
        assert (asset_dir / f"{name}-480.avif").exists()
        assert (asset_dir / f"{name}-1170.webp").exists()
        assert (asset_dir / f"{name}-2048.avif").exists()
