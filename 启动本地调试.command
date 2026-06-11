#!/bin/bash
# 双击此文件即可在两个终端窗口中启动 backend + frontend
DIR="$(cd "$(dirname "$0")" && pwd)"

# 打开 backend 窗口
osascript <<EOF
tell application "Terminal"
  activate
  do script "cd '$DIR' && bash start_backend.sh"
end tell
EOF

sleep 1

# 打开 frontend 窗口
osascript <<EOF
tell application "Terminal"
  activate
  do script "cd '$DIR' && bash start_frontend.sh"
end tell
EOF

echo "两个服务已在新窗口中启动"
echo "Backend: http://localhost:8000/docs"
echo "Frontend: http://localhost:5173"
