#!/bin/bash
# 本地启动 FastAPI backend（自动创建 venv + 安装依赖）
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/backend"

# 优先使用 3.12 / 3.11 / 3.13，避开 3.14（部分包暂无 wheel）
PYTHON=""
for candidate in python3.12 python3.11 python3.13 python3; do
  if command -v "$candidate" &>/dev/null; then
    PYTHON="$candidate"
    break
  fi
done
echo ">>> 使用 Python: $PYTHON ($($PYTHON --version))"

# 创建虚拟环境（只在首次运行时）
if [ ! -d ".venv" ]; then
  echo ">>> 创建 Python 虚拟环境..."
  $PYTHON -m venv .venv
fi

source .venv/bin/activate

echo ">>> 升级 pip / setuptools / wheel..."
pip install -q --upgrade pip setuptools wheel

echo ">>> 安装/更新依赖..."
pip install -r requirements.txt

# 创建本地数据目录
mkdir -p ../data/db ../data/thumbnails/256 ../data/thumbnails/1080

echo ">>> 启动 FastAPI (http://localhost:8000)"
echo ">>> API 文档: http://localhost:8000/docs"
echo ""

PHOTOS_ROOT="${PHOTOS_ROOT:-/Volumes/personal_folder/Photos}" \
DATABASE_URL="sqlite+aiosqlite:///$(pwd)/../data/db/photos.db" \
THUMBNAILS_DIR="$(pwd)/../data/thumbnails" \
WORKER_PROCESSES=4 \
CORS_ORIGINS='["http://localhost:5173","http://localhost:3000"]' \
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
