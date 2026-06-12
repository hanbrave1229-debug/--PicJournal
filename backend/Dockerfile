FROM python:3.12-slim

# 系统依赖：OpenCV headless + curl(healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 安装 Python 依赖
# face-recognition 需从源码编译 dlib（耗时 ~20min），NAS 上跳过
# 人脸识别功能已做优雅降级，缺失时自动禁用，不影响其他功能
COPY requirements.txt .
RUN grep -v "^face-recognition" requirements.txt > requirements-docker.txt \
    && pip install --no-cache-dir -r requirements-docker.txt

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
