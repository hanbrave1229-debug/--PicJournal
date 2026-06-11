#!/bin/bash
# 本地启动 Vue 3 frontend dev server
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/frontend"

if [ ! -d "node_modules" ]; then
  echo ">>> 安装 npm 依赖..."
  npm install
fi

echo ">>> 启动 Vite dev server (http://localhost:5173)"
npm run dev
