"""
Offline Reverse Geocoder — 100% local, zero network dependency.

Uses a local GeoNames SQLite database (data/geo/geonames.db) built from:
  - cities15000.txt   (GeoNames cities with population > 15,000)
  - admin1CodesASCII.txt  (province/state names)
  - countryInfo.txt   (country names)

Algorithm:
  1. Bounding-box pre-filter on (lat ± BBOX_DEG, lon ± BBOX_DEG)
  2. Haversine distance on candidates
  3. Return closest city + its admin1 + country

Usage:
    from app.services.geocoder import get_geocoder
    geo = get_geocoder()
    result = geo.reverse(lat=30.2741, lon=120.1551)
    # {'country': '中国', 'province': '浙江省', 'city': '杭州市'}

Run the build script once to populate the DB:
    python scripts/build_geo_db.py
"""
from __future__ import annotations

import logging
import math
import os
import sqlite3
from functools import lru_cache
from pathlib import Path
from typing import TypedDict

logger = logging.getLogger(__name__)

# Path to the geo SQLite database (built by scripts/build_geo_db.py)
_GEO_DB_PATH = Path(__file__).parent.parent.parent / "data" / "geo" / "geonames.db"

# Search bounding box radius in degrees (~110 km per degree)
_BBOX_DEG = 1.5

# Chinese province name mapping (GeoNames English → 中文)
_PROVINCE_ZH: dict[str, str] = {
    "Beijing": "北京", "Shanghai": "上海", "Tianjin": "天津", "Chongqing": "重庆",
    "Hebei": "河北", "Shanxi": "山西", "Inner Mongolia": "内蒙古", "Nei Mongol": "内蒙古",
    "Liaoning": "辽宁", "Jilin": "吉林", "Heilongjiang": "黑龙江",
    "Jiangsu": "江苏", "Zhejiang": "浙江", "Anhui": "安徽", "Fujian": "福建",
    "Jiangxi": "江西", "Shandong": "山东", "Henan": "河南", "Hubei": "湖北",
    "Hunan": "湖南", "Guangdong": "广东", "Guangxi": "广西", "Hainan": "海南",
    "Sichuan": "四川", "Guizhou": "贵州", "Yunnan": "云南", "Tibet": "西藏",
    "Xizang": "西藏", "Shaanxi": "陕西", "Gansu": "甘肃", "Qinghai": "青海",
    "Ningxia": "宁夏", "Xinjiang": "新疆",
    "Hong Kong": "香港", "Macao": "澳门", "Macau": "澳门", "Taiwan": "台湾",
}
_MUNICIPALITIES = {"北京", "上海", "天津", "重庆"}
_AUTONOMOUS_REGIONS = {"内蒙古", "广西", "西藏", "宁夏", "新疆"}


class GeoResult(TypedDict):
    country: str
    province: str
    city: str


class OfflineGeocoder:
    """
    Thread-safe, lazy-loading geocoder backed by a local SQLite DB.
    Falls back gracefully when the DB is not available.
    """

    def __init__(self, db_path: Path = _GEO_DB_PATH) -> None:
        self._db_path = db_path
        self._conn: sqlite3.Connection | None = None
        self._available: bool | None = None  # None = not checked yet

    def _ensure_connection(self) -> bool:
        """Return True if DB is available and connection is open."""
        if self._available is False:
            return False
        if self._conn is not None:
            return True

        if not self._db_path.exists():
            logger.warning(
                "GeoNames DB not found at %s — run scripts/build_geo_db.py to build it",
                self._db_path,
            )
            self._available = False
            return False

        try:
            self._conn = sqlite3.connect(
                str(self._db_path),
                check_same_thread=False,
                timeout=5,
            )
            self._conn.row_factory = sqlite3.Row
            # Validate schema
            self._conn.execute("SELECT 1 FROM cities LIMIT 1")
            self._available = True
            logger.info("OfflineGeocoder: loaded GeoNames DB from %s", self._db_path)
            return True
        except Exception as exc:
            logger.error("OfflineGeocoder: failed to open DB — %s", exc)
            self._available = False
            return False

    def reverse(self, lat: float, lon: float) -> GeoResult | None:
        """
        Reverse-geocode (lat, lon) → {country, province, city}.
        Returns None if the DB is unavailable or no city is found within
        the bounding box.
        """
        if not self._ensure_connection():
            return None

        assert self._conn is not None

        # Try to select name_zh if the column exists (added in newer DB builds)
        _sel = "name, name_zh, admin1_name, country_name, lat, lon"
        try:
            rows = self._conn.execute(
                f"""
                SELECT {_sel}
                FROM cities
                WHERE lat BETWEEN ? AND ?
                  AND lon BETWEEN ? AND ?
                ORDER BY population DESC
                LIMIT 50
                """,
                (
                    lat - _BBOX_DEG, lat + _BBOX_DEG,
                    lon - _BBOX_DEG, lon + _BBOX_DEG,
                ),
            ).fetchall()
        except Exception:
            # Older DB without name_zh — fall back to basic columns
            _sel = "name, admin1_name, country_name, lat, lon"
            try:
                rows = self._conn.execute(
                    f"""
                    SELECT {_sel}
                    FROM cities
                    WHERE lat BETWEEN ? AND ?
                      AND lon BETWEEN ? AND ?
                    ORDER BY population DESC
                    LIMIT 50
                    """,
                    (
                        lat - _BBOX_DEG, lat + _BBOX_DEG,
                        lon - _BBOX_DEG, lon + _BBOX_DEG,
                    ),
                ).fetchall()
            except Exception as exc:
                logger.error("OfflineGeocoder: query failed — %s", exc)
                return None

        if not rows:
            # Expand bbox 3× for sparse regions
            try:
                rows = self._conn.execute(
                    f"""
                    SELECT {_sel}
                    FROM cities
                    WHERE lat BETWEEN ? AND ?
                      AND lon BETWEEN ? AND ?
                    ORDER BY population DESC
                    LIMIT 20
                    """,
                    (
                        lat - _BBOX_DEG * 3, lat + _BBOX_DEG * 3,
                        lon - _BBOX_DEG * 3, lon + _BBOX_DEG * 3,
                    ),
                ).fetchall()
            except Exception:
                return None

        if not rows:
            return None

        # Pick nearest by Haversine distance
        best = min(rows, key=lambda r: _haversine(lat, lon, r["lat"], r["lon"]))

        # Prefer Chinese name if stored in DB (name_zh column), fall back to name
        raw_city = best["name_zh"] if "name_zh" in best.keys() and best["name_zh"] else best["name"] or ""
        province = best["admin1_name"] or ""
        country  = best["country_name"] or ""

        # Translate province to Chinese and append proper suffix
        if country in ("China", "中国") and province:
            zh = _PROVINCE_ZH.get(province, "")
            if zh:
                if zh in _MUNICIPALITIES:
                    province = zh + "市"
                elif zh in _AUTONOMOUS_REGIONS:
                    province = zh + "自治区"
                elif zh in ("香港", "澳门", "台湾"):
                    province = zh
                else:
                    province = zh + "省"
            elif not province.endswith(("省", "市", "区", "自治区")):
                province = province + "省"

        # City suffix
        city = raw_city
        if city and not city.endswith(("市", "县", "区", "镇", "岛", "乡")):
            city = city + "市"

        return GeoResult(country=country, province=province, city=city)

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None


# ── Haversine distance (km) ───────────────────────────────────────────────────

def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    dφ = math.radians(lat2 - lat1)
    dλ = math.radians(lon2 - lon1)
    a = math.sin(dφ / 2) ** 2 + math.cos(φ1) * math.cos(φ2) * math.sin(dλ / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ── Module-level singleton ────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def get_geocoder() -> OfflineGeocoder:
    """Return the module-level OfflineGeocoder singleton (created once)."""
    return OfflineGeocoder()
