"""The original guest gallery uses explicit framing, not accidental cover crops."""

from app.dashboard.media import build_slideshow_manifest


def test_original_gallery_marks_portrait_subject_safe(app):
    with app.test_request_context("/dashboard?tab=welcome"):
        slides = build_slideshow_manifest()

    assert len(slides) == 6
    assert [slide["id"] for slide in slides] == [
        "DSC06660", "DSC06692", "DSC06717",
        "DSC06785", "DSC06855", "DSC06882",
    ]
    assert [slide["fit"] for slide in slides] == [
        "cover", "cover", "contain", "cover", "cover", "cover",
    ]
    assert slides[2]["positionDesktop"] == "50% 50%"
    assert all(slide["fallback"].startswith("/static/") for slide in slides)
    assert all("positionMobile" in slide for slide in slides)
