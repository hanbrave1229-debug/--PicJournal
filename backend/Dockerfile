FROM python:3.12-slim

# 系统依赖：OpenCV headless + curl(healthcheck) + cmake/build-essential/git for dlib
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    curl \
    git \
    cmake \
    build-essential \
    libopenblas-dev \
    liblapack-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Step 1: 预编译 dlib（独立 layer，GHA cache 缓存，后续代码改动不重新编译）
RUN pip install --no-cache-dir "dlib==19.24.6"

# Step 2: 从官方 git 源安装 face_recognition_models（PyPI 版本有兼容性问题）
RUN pip install --no-cache-dir "git+https://github.com/ageitgey/face_recognition_models"

# Step 3: 安装其余 Python 依赖（face-recognition 此时跳过 dlib 和 models 的重复安装）
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
