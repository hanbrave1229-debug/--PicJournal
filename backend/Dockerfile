FROM python:3.12-slim

# 系统依赖：OpenCV headless + curl(healthcheck) + cmake/build-essential for dlib
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    curl \
    cmake \
    build-essential \
    libopenblas-dev \
    liblapack-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 预编译 dlib（独立 layer，由 GHA cache 缓存，后续代码改动不重新编译）
# face-recognition-models 提供人脸模型文件（纯 Python wheel，无需编译）
RUN pip install --no-cache-dir "dlib==19.24.6" "face-recognition-models==0.3.0"

# 安装其余 Python 依赖（含 face-recognition，此时 dlib 已装好，跳过重复编译）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

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
