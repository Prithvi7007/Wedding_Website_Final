from pathlib import Path


def test_registry_includes_target_and_zelle_options():
    template = Path("app/templates/tabs/registry.html").read_text(
        encoding="utf-8"
    )

    assert "View Target Registry" in template
    assert "A Gift Toward Our Future" in template
    assert "images/registry/adlin-zelle.jpeg" in template
    assert "Recipient: Adlin Lawrence" in template
    assert "Please confirm the recipient name before sending." in template


def test_registry_zelle_asset_exists():
    asset = Path("app/static/images/registry/adlin-zelle.jpeg")

    assert asset.exists()
    assert asset.stat().st_size > 20_000


def test_registry_zelle_layout_is_responsive():
    css = Path("app/static/css/information.css").read_text(
        encoding="utf-8"
    )
    block = css.split("/* REGISTRY ZELLE EXPERIENCE V1 */", 1)[1]

    assert ".registry-zelle-card {" in block
    assert ".registry-zelle-qr-link {" in block
    assert "@media (max-width: 980px)" in block
    assert "@media (max-width: 700px)" in block
