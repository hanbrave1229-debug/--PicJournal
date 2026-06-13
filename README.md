# 拾光手账 PicJournal

> 本地 NAS 私有照片管理系统 · 完全离线 · 零订阅 · 对标 Apple Photos

![License](https://img.shields.io/badge/license-MIT-green)
![Python](https://img.shields.io/badge/Python-3.11-blue)
![Vue](https://img.shields.io/badge/Vue-3-42b883)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110-009688)

---

## ✨ 功能特性

### 📸 照片管理
- **时间轴浏览** — 按日期分组，支持方形 / 原始比例切换
- **多选批量操作** — 批量删除、导出 ZIP、加入相册
- **软删除回收站** — 误删可恢复，物理文件不丢失
- **归档功能** — 重要照片单独归档，不污染主时间轴

### 🤖 AI 智能
- **批量 AI 打标** — 调用视觉大模型（Qwen2.5-VL / GPT-4o 等）自动生成图片描述和标签
- **CLIP 语义搜索** — 用自然语言搜照片（"海边日落"、"全家福"）
- **AI 照片日记** — 按月自动生成图文日记，支持 AI 主笔续写
- **多 AI 配置** — 支持同时配置多个 AI 服务商（OpenAI / Ollama / LM Studio），一键切换激活

### 👤 人物识别
- **离线人脸识别** — 基于 InsightFace（ONNX Runtime），特征向量不上传云端
- **DBSCAN 自动聚类** — 相似人脸自动归组，支持手动合并 / 重命名 / 隐藏 / 锁定
- **分页懒加载** — 人物列表默认每页 10 人，附带 4 张预览缩略图

### 🗺️ 地点
- **离线逆地理编码** — 基于 GeoNames 数据库，无需网络，支持中文城市名
- **城市照片墙** — 按城市聚合，封面缩略图，点击浏览该城市所有照片

### 📁 相册
- **手动相册** — 拖拽 / 批量创建，支持从已有照片库选取
- **ZIP 导入** — 上传 ZIP 包自动解压并建立相册（支持 Apple Photos 导出格式）
- **批量导出** — 选中照片或整本相册一键下载 ZIP

### 🔒 安全
- **API Key 加密存储** — Fernet 对称加密，密文存 DB，明文只在内存中使用
- **RSA-OAEP 传输加密** — 前端用服务端临时公钥加密 API Key 后再传输，防止中间人
- **完全本地运行** — 照片、人脸数据、AI 配置均存储在 NAS 本机

---

## 🏗️ 技术栈

| 层 | 技术 |
|---|---|
| 前端 | Vue 3 + Vite + TypeScript + Element Plus |
| 后端 | FastAPI + SQLAlchemy 2.0 async + SQLite (WAL) |
| 人脸识别 | InsightFace + ONNX Runtime（CPU）|
| 语义搜索 | CLIP + ONNX Runtime（CPU）|
| 地理编码 | GeoNames 离线数据库 |
| 部署 | Docker Compose |

---

## 🚀 快速安装

### 前置要求

- Docker & Docker Compose
- NAS 或 Linux 服务器（推荐 4 GB+ RAM）
- 照片存储目录（本地路径）

### 一、克隆仓库

```bash
git clone https://github.com/hanbrave1229-debug/--PicJournal.git
cd --PicJournal
```

### 二、配置 docker-compose.yml

```yaml
services:
  backend:
    image: ghcr.io/hanbrave1229-debug/picjournal-backend:latest
    container_name: picjournal-backend
    restart: unless-stopped
    ports:
      - "2526:8000"
    volumes:
      - /your/photos/path:/photos     # 照片目录（只读或读写均可）
      - /your/data/path:/app/data     # 数据库、缩略图、人脸数据（需持久化）
    environment:
      - PHOTOS_DIR=/photos
      - DATA_DIR=/app/data
      - TZ=Asia/Shanghai

  frontend:
    image: ghcr.io/hanbrave1229-debug/picjournal-frontend:latest
    container_name: picjournal-frontend
    restart: unless-stopped
    ports:
      - "2525:80"
    depends_on:
      - backend
```

将 `/your/photos/path` 替换为实际照片目录，`/your/data/path` 替换为数据持久化目录。

### 三、启动服务

```bash
docker compose up -d
```

浏览器访问 `http://<NAS-IP>:2525` 即可使用。

### 四、首次扫描

1. 进入「设置」→「扫描目录」，填写容器内照片路径（如 `/photos`）
2. 点击「开始扫描」，等待完成（首次较慢，需生成所有缩略图）
3. 扫描会自动提取 EXIF、GPS 信息、计算 ThumbHash 占位图

---

## ⚙️ 可选配置

### AI 打标

1. 进入「设置」→「智能设置」→「新增配置」
2. 填写服务商、API Key、Base URL、模型名称
3. 点击「测试连通性」确认正常，再点「激活」
4. 扫描页中点击「批量 AI 打标」即可开始

支持任意 OpenAI 兼容接口，包括 OpenAI、Ollama、LM Studio、Qwen API 等。

### 离线地理编码（中文城市名）

默认内置基础 GeoNames 数据。如需中文城市名，进容器执行：

```bash
docker exec -it picjournal-backend \
  python scripts/build_geo_db.py
```

> 需要访问 GeoNames 官网，可配置 `HTTP_PROXY` 环境变量走代理。

构建完成后重启容器，已入库照片需手动触发重新解析：

```bash
curl -X POST http://<NAS-IP>:2526/api/v1/geocoding/run
```

### 人脸识别

进入「人物」页面 → 点击「识别人脸」。首次运行会自动下载 InsightFace 模型文件（约 300 MB），之后识别全程离线。

---

## 📁 数据目录结构

```
/app/data/
├── picjournal.db        # SQLite 主数据库（照片元数据、相册、日记等）
├── secret.key           # Fernet 加密主密钥 ⚠️ 请务必备份
├── thumbnails/
│   └── faces/           # 人脸裁切图（person_{id}_p{photo_id}.jpg）
└── geo/
    └── geonames.db      # 离线地理编码数据库
```

> ⚠️ `secret.key` 丢失后，所有已加密存储的 AI API Key 将无法解密，需重新配置。

---

## 🔄 更新升级

```bash
docker compose pull
docker compose up -d
```

数据库迁移自动执行，无需手动操作。

---

## 🛠️ 本地开发

```bash
# 后端（Python 3.11+）
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# 前端
cd frontend
npm install
npm run dev
```

前端 dev server 默认将 `/api` 代理到 `http://localhost:8000`。

---

## 📄 License

MIT
