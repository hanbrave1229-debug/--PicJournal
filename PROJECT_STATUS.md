# PicJournal（拾光手账）项目状态 & 开发路线图

> 本地 NAS 私有照片管理系统，完全离线运行，对标 Apple Photos。
> 最后更新：2026-06-18

---

## 一、部署信息

| 项 | 值 |
|----|----|
| 运行地址 | `http://192.168.3.16:2526`（Tailscale: `100.66.1.3`） |
| 代码路径 | `~/Desktop/照片筛查/photo-manager/` |
| NAS 部署路径 | `/volume1/docker/picjournal/` |
| SSH | `ssh -p 9122 brave@192.168.3.16` |
| 镜像仓库 | GHCR `ghcr.io/hanbrave1229-debug/picjournal-{backend,frontend}:latest` |
| CI | push main → GitHub Actions 构建推送 `:latest` |

**部署流程**：本地 `git push` → 等 CI 构建 → NAS 上 `cd /volume1/docker/picjournal && docker compose pull && docker compose up -d`

> ⚠️ 频繁 SSH 重连会触发 NAS 防爆破封锁（表现为 Connection refused/closed，非密码错误）。
> 封锁时在 NAS 本地终端直接跑 docker 命令最快。

**关键 volume 挂载**（NAS docker-compose.yml）：
```
/home/brave/Photos          → /photos
.../picjournal/db           → /app/data/db
.../picjournal/thumbnails   → /app/data/thumbnails
.../picjournal/geo          → /app/data/geo
.../picjournal/secrets      → /app/data/secrets   (Fernet + JWT key，勿丢)
.../picjournal/imported     → /app/data/imported
.../picjournal/models       → /data/models        (CLIP 模型，2026-06-18 新增)
```

---

## 二、技术栈

| 层 | 技术 |
|---|---|
| 前端 | Vue 3 + Vite + TypeScript + Element Plus + Pinia |
| 后端 | FastAPI + SQLAlchemy 2.0 async + SQLite (WAL) |
| AI 推理 | ONNX Runtime (CPU) — InsightFace 人脸、CLIP 语义搜索 |
| 视觉 LLM | OpenAI 兼容端点（LM Studio/Ollama），从 `ai_model_configs` 表读配置 |
| 视频 | ffmpeg（抽帧缩略图 + ffprobe 时长） |
| 部署 | Docker Compose，NAS 单机 |

---

## 三、完成进度（核心架构 ≈85%）

| 模块 | 状态 | 说明 |
|------|------|------|
| 扫描入库 | ✅ 完善 | 增量扫描 + 定时自动扫描(可配置) + 启动清理孤儿任务 |
| 时间轴浏览 | ✅ 完善 | 拍摄时间 fallback 链：EXIF→文件名→文件mtime，年份限定 1990~当前年 |
| 缩略图 | ✅ 完善 | 256/1080 + ThumbHash 渐进占位 + 按需重生成 |
| 视频 | ✅ 完善 | ffmpeg 抽帧缩略图 + 流式播放 + 网格播放角标 + video 组件渲染 |
| 人脸识别 | ✅ 完善 | InsightFace + DBSCAN 聚类 + 合并/重命名/隐藏/锁定 + 分页 + preview_photos |
| 相册 | ✅ 完善 | 手动相册 + 智能相册(规则引擎 is_smart/smart_rules) |
| 地点 | ✅ 完善 | 离线逆地理编码(含中文省市) + 城市网格浏览 |
| 去重 | ✅ 完善 | MD5 + pHash |
| 照片堆叠 | ✅ 完善 | Stack（连拍/RAW+JPG 归组） |
| 质量评分 | ✅ 完善 | 清晰度(拉普拉斯方差) + 曝光 |
| 日记 | ✅ 完善 | 月历封面 + AI 主笔(generate-draft) + AI 润色(polish) |
| 导入导出 | ✅ 完善 | ZIP 批量导入导出 |
| AI 打标 | ✅ 完善 | VLM 自由描述 + 末尾关键词行，写回 ai_caption/ai_tags + XMP |
| 标签搜索 | ✅ 完善 | LIKE 匹配 ai_caption/ai_tags，无需 AI 服务 |
| AI 搜索 | ✅ 完善 | LLM 自然语言→SQL where 条件，需激活 AI 配置 |
| 向量搜索 | 🟡 引擎就绪 | CLIP ViT-B/32 ONNX 已下载、可用；**但全库嵌入未跑，暂搜不出结果** |
| 认证 | 🟡 中间档 | JWT 单管理员，HttpOnly cookie + header 双通道；图片接口免 token；**无多用户管理** |
| XMP 回写 | ✅ | sidecar 同步描述+标签 |
| 回收站/归档 | ✅ 完善 | 软删除双轨（is_deleted / is_archived） |
| 手机备份 | 🟡 PWA一版 | 扫描算MD5 + /backup/check + /backup/upload(服务端MD5兜底)；前端 /backup 页(选图→算MD5→查重→分批传) + PWA manifest/SW。**手动触发，非真后台自动(iOS PWA限制)** |
| 回忆 | ✅ 一版 | 那年今日 /memories/on-this-day(按年分组) + /cards 摘要；前端 /memories 页 |
| 相册分享 | ✅ 完善 | AlbumShare(token+bcrypt密码+过期)；管理API + 公开免登录API(白名单)；分享对话框(设密码/有效期/复制/撤销) + 公开访问页 /share/:token；过期访问返回410；每日清理过期链接 |

### 当前已知短板
- **CLIP 全库嵌入批处理未跑过** → 向量搜索搜不出结果（引擎和模型都就绪，缺一次批量 embedding）
- **手机备份非真后台** → PWA 只能"打开 App 点一下同步"，真后台自动需原生 App（路线图 C）
- **存量 md5_hash 未全填** → 老照片需一次全库重扫才会补齐 MD5（新 scanner 入库即算）
- **多用户被砍** → 认证只保留单管理员（UserRole 已留 ADMIN/USER 基础）

---

## 四、后续开发路线图（按 价值×工作量 排序）

### 🥇 P0 — 手机自动备份（决定项目生死）🟡 PWA 一版已完成
- 缺口最大：没有它用户还是要手动拖文件，无法替代 Google/Apple Photos
- 参考 Immich 的杀手锏
- 方案候选：
  - ✅ A. PWA（添加到主屏幕）+ 分片上传接口 —— **已实现一版**（手动触发同步）
  - B. 对接现成 App（PhotoSync/FolderSync）走 WebDAV/上传 API
  - C. 原生 App（React Native/Flutter）—— 真后台自动备份，待定
- 已落地：后端 `/backup/check` + `/backup/upload`（服务端 MD5 兜底）、扫描算 MD5；前端 `/backup` 页 + PWA manifest/SW
- 剩余：真后台自动（需原生 App）、断点续传、失败重试队列、上传完成通知

**判重设计（必做，否则会重复上传/入库）——两层机制：**
1. **手机端记账（优化层，省流量/电）**：App 本地库记录已备份照片的 identifier（本地 ID + mtime），每次只挑没备份过的发送。主力机制，但不保证正确性（换机/重装/清缓存会丢账本）。
2. **服务端哈希去重（兜底层，保证正确性）**：上传接口收到文件先算 MD5，命中库中已有 `md5_hash` → 直接跳过不入库。复用现有 `dedup_service` + Photo 表 `md5_hash`/`phash` 字段。**这一层是绝不重复入库的根本保证，必须做进上传接口。**

| 场景 | 处理 |
|------|------|
| 换手机/重装 App | 手机账本没了 → 服务端 MD5 兜底，不重复 |
| 导出再导入(轻微压缩) | MD5 变、pHash 接近 → 可选 pHash 做近似重复提示 |
| 修过的照片(裁剪/滤镜) | MD5+pHash 都变 → 视为新照片(符合预期) |
| 手机删、NAS 还在 | 备份单向，不联动删除(安全) |

### 🥈 P1 — CLIP 全库嵌入 + 回忆功能 🔨 开发中
- 先把全库 embedding 跑起来，向量搜索才真正可用（"夕阳""笑脸"语义搜索）
- 触发方式：semantic API 的批量嵌入入口（CPU 密集，建议夜间跑，3000 张约 30-60 分钟）
- 顺带做 **"那年今日 / 智能回忆"**：基于已有 taken_at + 人脸 + 地点自动生成精选集
- 工作量：小（复用已有数据）　价值：高

### 🥉 P2 — 分享 & 协作 🟡 分享已完成
- ✅ 分享链接（密码 + 过期时间）、相册分享给家人 —— **已完成**（AlbumShare + 公开访问页 /share/:token + 每日清理过期链接）
- ⬜ 多用户回归（认证已留 ADMIN/USER 角色基础，UI/逻辑未做）
- 工作量：中　价值：中

### 候选 — 体验打磨
- 大图基础编辑（裁剪/旋转/滤镜）
- 地图视图（照片在地图上打点，替代当前城市网格）
- HEIC / Live Photo 支持
- 虚拟滚动（库 10w+ 张时的性能）

**建议执行顺序**：先跑通 CLIP 全库嵌入（半天，立刻验证向量搜索价值）→ 主攻手机自动备份（最大缺口）。

---

## 五、重要技术约定 & 踩过的坑

- **SQLite WAL**：禁用 `BEGIN IMMEDIATE` 事件监听器（会导致并发打标 database is locked）
- **并发会话**：每个并发 asyncio task 必须用独立 AsyncSession，禁止共享
- **推理模型**：可能返回 `content: null`，真实内容在 `reasoning_content`，需 fallback
- **PhotoResponse**：用自定义 `from_orm()` 而非 `model_validate`（有派生字段）
- **图片接口免 auth**：thumbnails/persons.crops/videos/photos 前缀在中间件白名单（`<img>` 标签带不了 header）
- **nginx**：静态文件正则需排除 `/api/` 前缀，否则 `.jpg` 结尾的 API 路径被当静态文件 404
- **CLIP tokenizer**：`\p{L}`/`\p{N}` 需 `regex` 模块，stdlib `re` 不支持
- **CLIP 模型**：HF 仓库 `Xenova/clip-vit-base-patch32` 文件名为 `onnx/vision_model.onnx`/`text_model.onnx` + 根目录 `vocab.json`/`merges.txt`
- **拍摄时间**：fallback 链 EXIF→文件名(限 1990~当前年)→mtime，避免堆到入库日
- **secrets volume**：Fernet + JWT key 必须持久化挂载，否则重建容器后旧密文/token 全失效

---

## 六、常用运维命令

```bash
# 验证 Python 语法
find backend/app -name "*.py" | xargs python -m py_compile
# 前端类型检查
cd frontend && npx vue-tsc --noEmit
# 查看后端路由
grep "include_router" backend/app/api/v1/__init__.py

# NAS 部署（本地终端最稳）
cd /volume1/docker/picjournal && docker compose pull && docker compose up -d

# 触发扫描（容器内，需 JWT）
# 生成 token: auth_service.create_token(user)，再 curl POST /api/v1/scan/start

# CLIP 模型下载（容器内，需代理）
docker exec photo-manager-backend sh -c \
  'HTTPS_PROXY=http://172.17.0.1:20171 python3 -c "from app.core import clip_engine; print(clip_engine.is_available())"'
```
