"""
XMP Sidecar 双向同步服务
========================
读取/写入与照片同名的 .xmp 文件（photo.jpg → photo.jpg.xmp 或 photo.xmp）。
兼容 digiKam、Lightroom、Adobe Bridge。

命名空间:
  dc:     http://purl.org/dc/elements/1.1/
  xmp:    http://ns.adobe.com/xap/1.0/
  exif:   http://ns.adobe.com/exif/1.0/
  lr:     http://ns.adobe.com/lightroom/1.0/

字段映射:
  Photo.ai_caption  ↔  dc:description
  Photo.ai_tags     ↔  dc:subject (JSON array → rdf:Bag)
  Photo.city        ↔  (read-only; written from GPS data)
  Photo.taken_at    ↔  xmp:CreateDate  (read-only from XMP)
"""
from __future__ import annotations

import json
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── Namespaces ─────────────────────────────────────────────────────────────────
NS = {
    "x":    "adobe:ns:meta/",
    "rdf":  "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "dc":   "http://purl.org/dc/elements/1.1/",
    "xmp":  "http://ns.adobe.com/xap/1.0/",
    "exif": "http://ns.adobe.com/exif/1.0/",
    "lr":   "http://ns.adobe.com/lightroom/1.0/",
    "tiff": "http://ns.adobe.com/tiff/1.0/",
}

# Register prefixes so ElementTree serialises with correct prefixes
for _prefix, _uri in NS.items():
    ET.register_namespace(_prefix, _uri)

_RDF_ABOUT = f"{{{NS['rdf']}}}about"
_RDF_BAG   = f"{{{NS['rdf']}}}Bag"
_RDF_LI    = f"{{{NS['rdf']}}}li"
_RDF_DESC  = f"{{{NS['rdf']}}}Description"


# ── Public read API ────────────────────────────────────────────────────────────

class XmpData:
    """Parsed XMP metadata extracted from a sidecar file."""
    title:       str | None = None
    description: str | None = None   # maps to dc:description
    tags:        list[str] = []       # maps to dc:subject
    rating:      int | None = None    # xmp:Rating (0–5)
    create_date: datetime | None = None  # xmp:CreateDate
    city:        str | None = None
    country:     str | None = None


def sidecar_path(photo_path: str) -> Path:
    """Return preferred sidecar path: photo.jpg → photo.jpg.xmp"""
    return Path(photo_path + ".xmp")


def alt_sidecar_path(photo_path: str) -> Path:
    """Alternate convention: photo.jpg → photo.xmp"""
    p = Path(photo_path)
    return p.with_suffix(".xmp")


def find_sidecar(photo_path: str) -> Path | None:
    """Find existing sidecar (preferred first, then alternate)."""
    p = sidecar_path(photo_path)
    if p.exists():
        return p
    a = alt_sidecar_path(photo_path)
    if a.exists():
        return a
    return None


def read_sidecar(photo_path: str) -> XmpData | None:
    """
    Parse XMP sidecar adjacent to photo_path.
    Returns None if no sidecar found.
    """
    path = find_sidecar(photo_path)
    if not path:
        return None
    try:
        return _parse_xmp(path)
    except Exception as exc:
        logger.warning("XMP parse error %s: %s", path, exc)
        return None


# ── Public write API ───────────────────────────────────────────────────────────

def write_sidecar(
    photo_path: str,
    *,
    description: str | None = None,
    tags: list[str] | None = None,
    rating: int | None = None,
    title: str | None = None,
) -> Path:
    """
    Write (or update) a .xmp sidecar adjacent to photo_path.
    Returns the path of the written sidecar.
    Any kwarg left as None is not written (existing value preserved).
    """
    sidecar = sidecar_path(photo_path)

    # Load existing sidecar if present, otherwise build fresh
    if sidecar.exists():
        try:
            tree = ET.parse(str(sidecar))
            root = tree.getroot()
        except ET.ParseError:
            root = _make_xmpmeta_root()
    else:
        root = _make_xmpmeta_root()

    desc = _get_or_create_rdf_description(root)

    if title is not None:
        _set_alt_text(desc, f"{{{NS['dc']}}}title", title)
    if description is not None:
        _set_alt_text(desc, f"{{{NS['dc']}}}description", description)
    if tags is not None:
        _set_bag(desc, f"{{{NS['dc']}}}subject", tags)
        _set_bag(desc, f"{{{NS['lr']}}}hierarchicalSubject", tags)
    if rating is not None:
        _set_attr(desc, f"{{{NS['xmp']}}}Rating", str(max(0, min(5, rating))))

    # Stamp modification date
    _set_attr(desc, f"{{{NS['xmp']}}}MetadataDate",
              datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00"))

    # Write
    ET.indent(root, space="  ")
    tree_out = ET.ElementTree(root)
    with open(sidecar, "wb") as f:
        f.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
        tree_out.write(f, encoding="utf-8", xml_declaration=False)
    return sidecar


# ── Parsing helpers ────────────────────────────────────────────────────────────

def _parse_xmp(path: Path) -> XmpData:
    tree = ET.parse(str(path))
    root = tree.getroot()

    data = XmpData()
    data.tags = []

    # Walk all rdf:Description elements
    for desc in root.iter(_RDF_DESC):
        # dc:title
        t = _get_alt_text(desc, f"{{{NS['dc']}}}title")
        if t:
            data.title = t

        # dc:description
        d = _get_alt_text(desc, f"{{{NS['dc']}}}description")
        if d:
            data.description = d

        # dc:subject (tags)
        subj = desc.find(f"{{{NS['dc']}}}subject")
        if subj is not None:
            bag = subj.find(_RDF_BAG)
            if bag is not None:
                for li in bag.findall(_RDF_LI):
                    if li.text:
                        data.tags.append(li.text.strip())

        # xmp:Rating
        r = desc.get(f"{{{NS['xmp']}}}Rating") or _get_child_text(desc, f"{{{NS['xmp']}}}Rating")
        if r is not None:
            try:
                data.rating = int(r)
            except ValueError:
                pass

        # xmp:CreateDate
        cd = desc.get(f"{{{NS['xmp']}}}CreateDate") or _get_child_text(desc, f"{{{NS['xmp']}}}CreateDate")
        if cd:
            data.create_date = _parse_xmp_date(cd)

    return data


def _get_alt_text(parent: ET.Element, tag: str) -> str | None:
    """Extract first text value from rdf:Alt/rdf:li structure."""
    el = parent.find(tag)
    if el is None:
        return None
    alt = el.find(f"{{{NS['rdf']}}}Alt")
    if alt is not None:
        li = alt.find(_RDF_LI)
        return li.text if li is not None else None
    return el.text


def _get_child_text(parent: ET.Element, tag: str) -> str | None:
    el = parent.find(tag)
    return el.text if el is not None else None


def _parse_xmp_date(s: str) -> datetime | None:
    """Parse ISO 8601 date string (partial)."""
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%Y:%m:%d %H:%M:%S"):
        try:
            return datetime.strptime(s[:len(fmt) + 5].strip(), fmt)
        except ValueError:
            continue
    return None


# ── Building helpers ───────────────────────────────────────────────────────────

def _make_xmpmeta_root() -> ET.Element:
    xmpmeta = ET.Element(f"{{{NS['x']}}}xmpmeta")
    xmpmeta.set(f"{{{NS['x']}}}xmptk", "拾光手账 XMP Writer 1.0")
    rdf = ET.SubElement(xmpmeta, f"{{{NS['rdf']}}}RDF")
    desc = ET.SubElement(rdf, _RDF_DESC)
    desc.set(_RDF_ABOUT, "")
    return xmpmeta


def _get_or_create_rdf_description(root: ET.Element) -> ET.Element:
    rdf = root.find(f"{{{NS['rdf']}}}RDF")
    if rdf is None:
        rdf = ET.SubElement(root, f"{{{NS['rdf']}}}RDF")
    desc = rdf.find(_RDF_DESC)
    if desc is None:
        desc = ET.SubElement(rdf, _RDF_DESC)
        desc.set(_RDF_ABOUT, "")
    return desc


def _set_alt_text(desc: ET.Element, tag: str, value: str) -> None:
    el = desc.find(tag)
    if el is None:
        el = ET.SubElement(desc, tag)
    el.clear()
    alt = ET.SubElement(el, f"{{{NS['rdf']}}}Alt")
    li = ET.SubElement(alt, _RDF_LI)
    li.set(f"{{{NS['xml']}}}lang", "x-default")
    li.text = value


def _set_bag(desc: ET.Element, tag: str, values: list[str]) -> None:
    el = desc.find(tag)
    if el is None:
        el = ET.SubElement(desc, tag)
    el.clear()
    bag = ET.SubElement(el, _RDF_BAG)
    for v in values:
        li = ET.SubElement(bag, _RDF_LI)
        li.text = v


def _set_attr(desc: ET.Element, attr: str, value: str) -> None:
    desc.set(attr, value)
