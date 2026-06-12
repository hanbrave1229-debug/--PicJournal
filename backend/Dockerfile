FROM python:3.12-slim

# 系统依赖：OpenCV 需要 libgl1，curl 用于健康检查
# insightface 使用 ONNX Runtime，无需 cmake/dlib/build-essential
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libgl1-mesa-glx \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 安装 Python 依赖（insightface + onnxruntime 均有 Linux x86_64 预编译 wheel，无需编译）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 预下载 InsightFace buffalo_sc 模型（~25MB），避免首次运行时下载延迟
# 失败时不中断构建（离线环境或网络限制时跳过，首次运行再下载）
RUN python -c "\
from insightface.app import FaceAnalysis; \
app = FaceAnalysis(name='buffalo_sc', providers=['CPUExecutionProvider']); \
app.prepare(ctx_id=0)" || echo "[INFO] InsightFace model pre-download skipped"

# 复制应用代码
COPY app/ ./app/

# 复制初始化脚本（build_geo_db.py / fill_thumbhash.py）
COPY scripts/ ./scripts/

# 创建数据目录
RUN mkdir -p /app/data/db /app/data/thumbnails/256 /app/data/thumbnails/1080 /app/data/geo

EXPOSE 8000

COPY entrypoint.sh ./entrypoint.sh
RUN chmod +x entrypoint.sh

ENTRYPOINT ["./entrypoint.sh"]
