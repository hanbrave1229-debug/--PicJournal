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
        "South Korea": "韩国", "North Korea": "朝鲜", "France": "法国",
        "Germany": "德国", "United Kingdom": "英国", "Australia": "澳大利亚",
        "Canada": "加拿大", "Italy": "意大利", "Spain": "西班牙",
        "Russia": "俄罗斯", "Brazil": "巴西", "India": "印度",
        "Thailand": "泰国", "Singapore": "新加坡", "Malaysia": "马来西亚",
        # ── 亚洲 ──
        "Vietnam": "越南", "Indonesia": "印度尼西亚", "Philippines": "菲律宾",
        "Cambodia": "柬埔寨", "Laos": "老挝", "Myanmar": "缅甸", "Brunei": "文莱",
        "Timor Leste": "东帝汶", "Mongolia": "蒙古", "Nepal": "尼泊尔",
        "Bhutan": "不丹", "Bangladesh": "孟加拉国", "Sri Lanka": "斯里兰卡",
        "Maldives": "马尔代夫", "Pakistan": "巴基斯坦", "Afghanistan": "阿富汗",
        "Kazakhstan": "哈萨克斯坦", "Uzbekistan": "乌兹别克斯坦",
        "Turkmenistan": "土库曼斯坦", "Kyrgyzstan": "吉尔吉斯斯坦",
        "Tajikistan": "塔吉克斯坦", "Hong Kong": "中国香港", "Macao": "中国澳门",
        "Taiwan": "中国台湾",
        # ── 中东 ──
        "Iran": "伊朗", "Iraq": "伊拉克", "Israel": "以色列", "Jordan": "约旦",
        "Lebanon": "黎巴嫩", "Syria": "叙利亚", "Saudi Arabia": "沙特阿拉伯",
        "United Arab Emirates": "阿联酋", "Qatar": "卡塔尔", "Kuwait": "科威特",
        "Bahrain": "巴林", "Oman": "阿曼", "Yemen": "也门",
        "Palestinian Territory": "巴勒斯坦", "Turkey": "土耳其",
        "Cyprus": "塞浦路斯", "Georgia": "格鲁吉亚", "Armenia": "亚美尼亚",
        "Azerbaijan": "阿塞拜疆",
        # ── 欧洲 ──
        "The Netherlands": "荷兰", "Belgium": "比利时", "Luxembourg": "卢森堡",
        "Switzerland": "瑞士", "Austria": "奥地利", "Portugal": "葡萄牙",
        "Ireland": "爱尔兰", "Greece": "希腊", "Poland": "波兰", "Czechia": "捷克",
        "Slovakia": "斯洛伐克", "Hungary": "匈牙利", "Romania": "罗马尼亚",
        "Bulgaria": "保加利亚", "Croatia": "克罗地亚", "Slovenia": "斯洛文尼亚",
        "Serbia": "塞尔维亚", "Bosnia and Herzegovina": "波黑",
        "Montenegro": "黑山", "North Macedonia": "北马其顿", "Albania": "阿尔巴尼亚",
        "Kosovo": "科索沃", "Ukraine": "乌克兰", "Belarus": "白俄罗斯",
        "Moldova": "摩尔多瓦", "Lithuania": "立陶宛", "Latvia": "拉脱维亚",
        "Estonia": "爱沙尼亚", "Finland": "芬兰", "Sweden": "瑞典",
        "Norway": "挪威", "Denmark": "丹麦", "Iceland": "冰岛", "Monaco": "摩纳哥",
        "Andorra": "安道尔", "San Marino": "圣马力诺", "Vatican": "梵蒂冈",
        "Liechtenstein": "列支敦士登", "Malta": "马耳他", "Gibraltar": "直布罗陀",
        "Aland Islands": "奥兰群岛", "Faroe Islands": "法罗群岛",
        "Guernsey": "根西", "Jersey": "泽西", "Isle of Man": "马恩岛",
        "Svalbard and Jan Mayen": "斯瓦尔巴", "Greenland": "格陵兰",
        # ── 美洲 ──
        "Mexico": "墨西哥", "Guatemala": "危地马拉", "Belize": "伯利兹",
        "Honduras": "洪都拉斯", "El Salvador": "萨尔瓦多", "Nicaragua": "尼加拉瓜",
        "Costa Rica": "哥斯达黎加", "Panama": "巴拿马", "Cuba": "古巴",
        "Jamaica": "牙买加", "Haiti": "海地", "Dominican Republic": "多米尼加",
        "Bahamas": "巴哈马", "Barbados": "巴巴多斯", "Trinidad and Tobago": "特立尼达和多巴哥",
        "Puerto Rico": "波多黎各", "Colombia": "哥伦比亚", "Venezuela": "委内瑞拉",
        "Guyana": "圭亚那", "Suriname": "苏里南", "Ecuador": "厄瓜多尔",
        "Peru": "秘鲁", "Bolivia": "玻利维亚", "Paraguay": "巴拉圭",
        "Uruguay": "乌拉圭", "Argentina": "阿根廷", "Chile": "智利",
        "French Guiana": "法属圭亚那",
        # ── 非洲 ──
        "Egypt": "埃及", "Libya": "利比亚", "Tunisia": "突尼斯", "Algeria": "阿尔及利亚",
        "Morocco": "摩洛哥", "Western Sahara": "西撒哈拉", "Sudan": "苏丹",
        "South Sudan": "南苏丹", "Ethiopia": "埃塞俄比亚", "Eritrea": "厄立特里亚",
        "Djibouti": "吉布提", "Somalia": "索马里", "Kenya": "肯尼亚",
        "Uganda": "乌干达", "Tanzania": "坦桑尼亚", "Rwanda": "卢旺达",
        "Burundi": "布隆迪", "Nigeria": "尼日利亚", "Ghana": "加纳",
        "Ivory Coast": "科特迪瓦", "Senegal": "塞内加尔", "Mali": "马里",
        "Niger": "尼日尔", "Chad": "乍得", "Cameroon": "喀麦隆",
        "Gabon": "加蓬", "Republic of the Congo": "刚果（布）",
        "Democratic Republic of the Congo": "刚果（金）", "Angola": "安哥拉",
        "Zambia": "赞比亚", "Zimbabwe": "津巴布韦", "Malawi": "马拉维",
        "Mozambique": "莫桑比克", "Botswana": "博茨瓦纳", "Namibia": "纳米比亚",
        "South Africa": "南非", "Lesotho": "莱索托", "Eswatini": "斯威士兰",
        "Madagascar": "马达加斯加", "Mauritius": "毛里求斯", "Seychelles": "塞舌尔",
        "Comoros": "科摩罗", "Cabo Verde": "佛得角", "Mauritania": "毛里塔尼亚",
        "Gambia": "冈比亚", "Guinea": "几内亚", "Guinea-Bissau": "几内亚比绍",
        "Sierra Leone": "塞拉利昂", "Liberia": "利比里亚", "Togo": "多哥",
        "Benin": "贝宁", "Burkina Faso": "布基纳法索", "Central African Republic": "中非",
        "Equatorial Guinea": "赤道几内亚", "Sao Tome and Principe": "圣多美和普林西比",
        "Reunion": "留尼汪", "Mayotte": "马约特",
        # ── 大洋洲 ──
        "New Zealand": "新西兰", "Fiji": "斐济", "Papua New Guinea": "巴布亚新几内亚",
        "Solomon Islands": "所罗门群岛", "Vanuatu": "瓦努阿图", "Samoa": "萨摩亚",
        "Tonga": "汤加", "Kiribati": "基里巴斯", "Micronesia": "密克罗尼西亚",
        "Palau": "帕劳", "Marshall Islands": "马绍尔群岛", "Nauru": "瑙鲁",
        "Tuvalu": "图瓦卢", "New Caledonia": "新喀里多尼亚",
        "French Polynesia": "法属波利尼西亚", "Guam": "关岛",
        "American Samoa": "美属萨摩亚", "Cook Islands": "库克群岛",
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
