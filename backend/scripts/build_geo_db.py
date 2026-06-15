#!/usr/bin/env python3
"""
Build the local GeoNames SQLite database for offline reverse geocoding.

Downloads three files from GeoNames (geonames.org) and builds a compact
SQLite DB at:  backend/data/geo/geonames.db

Run once (or whenever you want to refresh the data):
    cd backend
    python scripts/build_geo_db.py

Data sources (public domain, Creative Commons Attribution 4.0):
  - cities15000.txt   ~25,000 cities worldwide (pop > 15,000)
  - admin1CodesASCII.txt  province / state names
  - countryInfo.txt       country names + ISO codes

The resulting DB is ~8 MB and fits comfortably on any NAS.
"""
from __future__ import annotations

import io
import os
import sqlite3
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────

DB_PATH = Path(__file__).parent.parent / "data" / "geo" / "geonames.db"
TEMP_DIR = Path(__file__).parent.parent / "data" / "geo" / "_tmp"

URLS = {
    "cities":  "https://download.geonames.org/export/dump/cities15000.zip",
    "admin1":  "https://download.geonames.org/export/dump/admin1CodesASCII.txt",
    "country": "https://download.geonames.org/export/dump/countryInfo.txt",
}

# GeoNames cities15000.txt column indices (tab-separated)
COL_GEONAMEID   = 0
COL_NAME        = 1   # UTF-8 city name
COL_ASCII_NAME  = 2
COL_ALT_NAMES   = 3
COL_LAT         = 4
COL_LON         = 5
COL_FEAT_CLASS  = 6
COL_FEAT_CODE   = 7
COL_COUNTRY     = 8   # ISO 2-letter
COL_CC2         = 9
COL_ADMIN1      = 10  # admin1 code
COL_ADMIN2      = 11
COL_ADMIN3      = 12
COL_ADMIN4      = 13
COL_POPULATION  = 14


# ── Helpers ───────────────────────────────────────────────────────────────────

def _download(url: str, label: str) -> bytes:
    print(f"  Downloading {label} ...", end=" ", flush=True)
    t0 = time.time()
    with urllib.request.urlopen(url, timeout=60) as resp:
        data = resp.read()
    print(f"{len(data) // 1024} KB  ({time.time() - t0:.1f}s)")
    return data


def _unzip_first(data: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        name = zf.namelist()[0]
        return zf.read(name).decode("utf-8", errors="replace")


# ── Build ─────────────────────────────────────────────────────────────────────

def build() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    if DB_PATH.exists():
        DB_PATH.unlink()
        print(f"Removed existing DB: {DB_PATH}")

    print("=== Building GeoNames offline DB ===")

    # 1. Download data
    cities_zip  = _download(URLS["cities"],  "cities15000.zip")
    admin1_txt  = _download(URLS["admin1"],  "admin1CodesASCII.txt").decode("utf-8", errors="replace")
    country_txt = _download(URLS["country"], "countryInfo.txt").decode("utf-8", errors="replace")

    # 2. Parse admin1 codes → name  (key: "CC.admin1code")
    admin1: dict[str, str] = {}
    for line in admin1_txt.splitlines():
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) >= 2:
            admin1[parts[0]] = parts[1]

    # 3. Parse country codes → name
    country: dict[str, str] = {}
    for line in country_txt.splitlines():
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) >= 5:
            iso2  = parts[0]
            name  = parts[4]
            country[iso2] = name

    # 4. Chinese translations for the most common countries/provinces
    #    (GeoNames uses English names; these replacements improve display)
    COUNTRY_ZH: dict[str, str] = {
        "China": "中国", "United States": "美国", "Japan": "日本",
        "South Korea": "韩国", "France": "法国", "Germany": "德国",
        "United Kingdom": "英国", "Australia": "澳大利亚", "Canada": "加拿大",
        "Italy": "意大利", "Spain": "西班牙", "Russia": "俄罗斯",
        "Brazil": "巴西", "India": "印度", "Thailand": "泰国",
        "Singapore": "新加坡", "Malaysia": "马来西亚",
    }

    # 5. Parse cities15000.txt
    print("  Parsing cities15000 ...", end=" ", flush=True)
    cities_txt = _unzip_first(cities_zip)
    rows: list[tuple] = []
    for line in cities_txt.splitlines():
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 15:
            continue
        try:
            lat = float(parts[COL_LAT])
            lon = float(parts[COL_LON])
            pop = int(parts[COL_POPULATION] or "0")
        except ValueError:
            continue

        cc       = parts[COL_COUNTRY]
        a1_code  = parts[COL_ADMIN1]
        a1_key   = f"{cc}.{a1_code}"

        city_name    = parts[COL_NAME]
        alt_names    = parts[COL_ALT_NAMES] if len(parts) > COL_ALT_NAMES else ""
        admin1_name  = admin1.get(a1_key, "")
        country_name_en = country.get(cc, cc)
        country_name = COUNTRY_ZH.get(country_name_en, country_name_en)

        # Extract Chinese name from alternatenames. Prefer a token that contains
        # CJK ideographs but NO Japanese kana / Korean hangul, so we don't pick a
        # Japanese or Korean alternate (e.g. "サムドゥプツェ区") for a Chinese city.
        def _has_cjk(s: str) -> bool:
            return any("一" <= ch <= "鿿" for ch in s)

        def _has_kana_or_hangul(s: str) -> bool:
            return any(
                ("぀" <= ch <= "ヿ")  # hiragana + katakana
                or ("가" <= ch <= "힣")  # hangul syllables
                for ch in s
            )

        name_zh = ""
        fallback_zh = ""
        for tok in alt_names.split(","):
            tok = tok.strip()
            if not tok or not _has_cjk(tok):
                continue
            if _has_kana_or_hangul(tok):
                fallback_zh = fallback_zh or tok  # last resort only
                continue
            name_zh = tok
            break  # first pure-CJK token wins
        if not name_zh:
            name_zh = fallback_zh

        rows.append((city_name, name_zh, admin1_name, country_name, lat, lon, pop, cc))

    print(f"{len(rows):,} cities")

    # 6. Write SQLite
    print(f"  Writing SQLite → {DB_PATH} ...", end=" ", flush=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cities (
            id           INTEGER PRIMARY KEY,
            name         TEXT NOT NULL,
            name_zh      TEXT,
            admin1_name  TEXT,
            country_name TEXT,
            lat          REAL NOT NULL,
            lon          REAL NOT NULL,
            population   INTEGER DEFAULT 0,
            country_code TEXT
        )
    """)
    conn.executemany(
        "INSERT INTO cities (name, name_zh, admin1_name, country_name, lat, lon, population, country_code) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    # Spatial index via regular B-tree on (lat, lon)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cities_lat ON cities(lat)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cities_lon ON cities(lon)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cities_latlon ON cities(lat, lon)")
    conn.commit()

    size_kb = DB_PATH.stat().st_size // 1024
    print(f"{size_kb:,} KB")
    conn.close()

    print(f"\n✅  GeoNames DB built successfully: {DB_PATH}")
    print(f"    {len(rows):,} cities  |  {size_kb:,} KB on disk")


if __name__ == "__main__":
    build()
