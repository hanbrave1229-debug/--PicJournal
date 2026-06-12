#!/bin/sh
set -e

# 首次启动自动构建离线地理编码数据库（约 30 秒）
# 已存在则跳过，不重复下载
if [ ! -f /app/data/geo/geonames.db ]; then
    echo "[picjournal] GeoNames DB not found, building now (one-time ~30s)..."
    python scripts/build_geo_db.py
    echo "[picjournal] GeoNames DB ready."
fi

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
