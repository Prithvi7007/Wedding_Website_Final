from pathlib import Path


def test_registry_restores_target_keepsake_and_adds_cash_fund():
    template = Path("app/templates/tabs/registry.html").read_text(
        encoding="utf-8"
    )

    expected = [
        "View Target Registry",
        "Wedding Registry",
        "Cash Fund",
        "A Gift Toward Our Future",
        "Adlin's Zelle QR",
        "Prithvi's Zelle QR",
        "For Our Next Chapter",
    ]

    for text in expected:
        assert text in template


def test_registry_uses_two_separate_qr_assets():
    template = Path("app/templates/tabs/registry.html").read_text(
        encoding="utf-8"
    )

    assert "images/registry/adlin-zelle.jpeg" in template
    assert "images/registry/prithvi-zelle.jpeg" in template
    assert "registry-zelle-qr" not in template

    adlin = Path("app/static/images/registry/adlin-zelle.jpeg")
    prithvi = Path("app/static/images/registry/prithvi-zelle.jpeg")

    assert adlin.exists()
    assert prithvi.exists()
    assert adlin.stat().st_size > 20_000
    assert prithvi.stat().st_size > 20_000


def test_dual_registry_layout_is_responsive():
    css = Path("app/static/css/information.css").read_text(
        encoding="utf-8"
    )
    block = css.split("/* REGISTRY DUAL CASH FUND V2 */", 1)[1]

    assert ".registry-panel-split {" in block
    assert ".registry-stack {" in block
    assert ".cash-fund-actions {" in block
    assert "@media (max-width: 980px)" in block
    assert "@media (max-width: 700px)" in block
