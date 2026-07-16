from __future__ import annotations

from dataclasses import dataclass

from app.assets import asset_url


@dataclass(frozen=True, slots=True)
class SlideshowSource:
    name: str
    position_desktop: str
    position_mobile: str


SLIDESHOW_SOURCES: tuple[SlideshowSource, ...] = (
    SlideshowSource("DSC06660", "61% 48%", "68% center"),
    SlideshowSource("DSC06692", "63% 45%", "68% center"),
    SlideshowSource("DSC06717", "68% 50%", "72% center"),
    SlideshowSource("DSC06785", "59% 48%", "65% center"),
    SlideshowSource("DSC06855", "64% 44%", "69% center"),
    SlideshowSource("DSC06882", "67% 50%", "71% center"),
)

WIDTHS: tuple[int, ...] = (480, 768, 1170, 1600, 2048)


def _asset_url(name: str, width: int, extension: str) -> str:
    return asset_url(f"images/slideshow/{name}-{width}.{extension}")


def _srcset(name: str, extension: str) -> str:
    return ", ".join(
        f"{_asset_url(name, width, extension)} {width}w"
        for width in WIDTHS
    )


def build_slideshow_manifest() -> list[dict[str, str]]:
    return [
        {
            "id": source.name,
            "avifSrcset": _srcset(source.name, "avif"),
            "webpSrcset": _srcset(source.name, "webp"),
            "fallback": _asset_url(source.name, 1170, "webp"),
            "positionDesktop": source.position_desktop,
            "positionMobile": source.position_mobile,
        }
        for source in SLIDESHOW_SOURCES
    ]
