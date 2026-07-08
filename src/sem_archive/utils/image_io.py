from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageOps

Image.MAX_IMAGE_PIXELS = None

TIFF_SUFFIXES = {".tif", ".tiff"}
DIRECT_PPT_SUFFIXES = {".jpg", ".jpeg", ".png"}


def load_thumbnail(path: Path, max_size: tuple[int, int] = (240, 240)) -> Image.Image | None:
    try:
        with Image.open(path) as img:
            image = ImageOps.exif_transpose(img)
            image = image.convert("RGB")
            image.thumbnail(max_size)
            return image.copy()
    except Exception:
        return None


def prepare_for_pptx(path: Path, cache_dir: Path) -> Path:
    """PPT埋め込み用パスを返す。TIFFはロスレスPNGへ変換する。"""
    suffix = path.suffix.lower()
    if suffix in DIRECT_PPT_SUFFIXES:
        return path
    if suffix in TIFF_SUFFIXES:
        cache_dir.mkdir(parents=True, exist_ok=True)
        out = cache_dir / f"{path.stem}_{abs(hash(path.as_posix()))}.png"
        if not out.exists() or out.stat().st_mtime < path.stat().st_mtime:
            with Image.open(path) as img:
                converted = ImageOps.exif_transpose(img)
                if converted.mode not in ("RGB", "RGBA", "L"):
                    converted = converted.convert("RGB")
                converted.save(out, format="PNG", compress_level=1)
        return out
    # その他は再エンコードせずそのまま試す
    return path
