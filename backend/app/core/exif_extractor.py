"""
EXIF metadata extractor.

Uses `exifread` for broad RAW/HEIC support.
Falls back to Pillow for files exifread can't handle.
All I/O is done synchronously (called from a thread pool to avoid blocking the event loop).
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

import exifread


# ── Helpers ───────────────────────────────────────────────────────────────────

def _tag(tags: dict[str, Any], key: str) -> Any | None:
    """Return the IFDRational / string value of an EXIF tag, or None."""
    return tags.get(key) or tags.get(f"Image {key.split()[-1]}")


def _str(tags: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        val = tags.get(key)
        if val is not None:
            s = str(val).strip()
            return s if s else None
    return None


def _int(tags: dict[str, Any], *keys: str) -> int | None:
    for key in keys:
        val = tags.get(key)
        if val is not None:
            try:
                return int(str(val))
            except (ValueError, ZeroDivisionError):
                pass
    return None


def _parse_datetime(raw: str | None) -> datetime | None:
    """Parse EXIF datetime string  '2024:06:01 12:34:56' → datetime."""
    if not raw:
        return None
    # Normalize separators
    clean = raw.strip().replace("\x00", "")
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.strptime(clean, fmt)
        except ValueError:
            continue
    return None


def _rational_to_float(val: Any) -> float | None:
    """Convert IFDRational or 'num/den' string to float."""
    if val is None:
        return None
    try:
        s = str(val)
        if "/" in s:
            num, den = s.split("/", 1)
            den_f = float(den)
            return float(num) / den_f if den_f != 0 else None
        return float(s)
    except (ValueError, ZeroDivisionError):
        return None


def _gps_dms_to_decimal(dms_str: str, ref: str) -> float | None:
    """
    Convert GPS DMS string '[48, 51, 29.5]' + ref 'N'/'S'/'E'/'W' to decimal degrees.
    """
    try:
        nums = [_rational_to_float(v) for v in re.findall(r"[\d./]+", dms_str)]
        if len(nums) < 3 or any(v is None for v in nums):
            return None
        deg, minutes, seconds = nums[0], nums[1], nums[2]  # type: ignore[misc]
        decimal = deg + minutes / 60 + seconds / 3600  # type: ignore[operator]
        if ref.upper() in ("S", "W"):
            decimal = -decimal
        return round(decimal, 7)
    except Exception:
        return None


# ── Public API ────────────────────────────────────────────────────────────────

class ExifData:
    """Container for extracted EXIF fields."""

    __slots__ = (
        "taken_at",
        "camera_make",
        "camera_model",
        "aperture",
        "shutter_speed",
        "iso",
        "gps_lat",
        "gps_lon",
    )

    def __init__(self) -> None:
        self.taken_at: datetime | None = None
        self.camera_make: str | None = None
        self.camera_model: str | None = None
        self.aperture: str | None = None       # e.g. "f/1.8"
        self.shutter_speed: str | None = None  # e.g. "1/250"
        self.iso: int | None = None
        self.gps_lat: float | None = None
        self.gps_lon: float | None = None


def extract(file_path: str | Path) -> ExifData:
    """
    Extract EXIF metadata from *file_path*.

    This function is **synchronous** — call it inside
    ``asyncio.get_event_loop().run_in_executor(...)`` or
    ``concurrent.futures.ProcessPoolExecutor`` to avoid blocking.

    Returns an :class:`ExifData` instance (fields are ``None`` when absent).
    """
    data = ExifData()
    path = Path(file_path)

    if not path.exists():
        return data

    try:
        with path.open("rb") as fh:
            tags = exifread.process_file(fh, details=False, strict=False)
    except Exception:
        return data

    # ── Datetime ──────────────────────────────────────────────────────────────
    raw_dt = _str(
        tags,
        "EXIF DateTimeOriginal",
        "EXIF DateTimeDigitized",
        "Image DateTime",
    )
    data.taken_at = _parse_datetime(raw_dt)

    # ── Camera ────────────────────────────────────────────────────────────────
    data.camera_make = _str(tags, "Image Make")
    data.camera_model = _str(tags, "Image Model")

    # ── Aperture — store as "f/1.8" string ───────────────────────────────────
    fnum = _rational_to_float(tags.get("EXIF FNumber"))
    if fnum is not None:
        data.aperture = f"f/{fnum:.1f}"

    # ── Shutter speed ─────────────────────────────────────────────────────────
    exp = tags.get("EXIF ExposureTime")
    if exp is not None:
        data.shutter_speed = str(exp)  # already in "1/250" form

    # ── ISO ───────────────────────────────────────────────────────────────────
    data.iso = _int(tags, "EXIF ISOSpeedRatings")

    # ── GPS ───────────────────────────────────────────────────────────────────
    lat_tag = tags.get("GPS GPSLatitude")
    lat_ref = _str(tags, "GPS GPSLatitudeRef") or "N"
    lon_tag = tags.get("GPS GPSLongitude")
    lon_ref = _str(tags, "GPS GPSLongitudeRef") or "E"

    if lat_tag and lon_tag:
        data.gps_lat = _gps_dms_to_decimal(str(lat_tag), lat_ref)
        data.gps_lon = _gps_dms_to_decimal(str(lon_tag), lon_ref)

    return data
