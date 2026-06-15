# PicJournal 任务追踪

> 格式：`[x]` 已完成 · `[ ]` 待办 · P0 已完成项附解决方案

---

## ✅ 已完成

### P0 — Bug 修复

#### [x] API Key 重启后解密失败
**现象**：重启容器后所有 AI 配置显示 `****`，测试报"未配置 API Key"。  
**根因**：`secret.key` 存于 `/app/data/secret.key`，但 docker-compose 只挂载了子目录（`/app/data/db`、`/app/data/thumbnails` 等），根目录未持久化，每次重启重新生成密钥导致旧 Key 全部无法解密。  
**方案**：
- `docker-compose.yml` 新增 `data/secrets:/app/data/secrets` 卷
- `crypto.py` 密钥路径改为 `/app/data/secrets/secret.key`
- `ai_configs_api.py` 区分"未配置"和"解密失败"两种错误
- `Settings.vue` Key 字段解密失败时显示 ⚠ 橙色警告
- **NAS 操作**：重新部署后需在设置页重新填写一次 API Key

#### [x] diary generate-draft 报"AI API Key 未配置"
**现象**：即使已在 ai_configs 配置并激活模型，日记生成草稿仍报错。  
**根因**：`diary.py` 检查的是旧全局 `config` 表的 `ai_api_key` 字段，而新系统用 `ai_configs` 表。  
**方案**：`diary.py` 改为查询 `AiModelConfig.is_active=True` 做前置校验，service 层本已读 active config，传空参数即可。

#### [x] geocoding/run 返回 422
**根因**：FastAPI 路由 `/{photo_id}: int` 注册在 `/run` 之前，"run" 被当作 int 解析失败。  
**方案**：调整路由顺序，`/run` 必须在 `/{photo_id}` 之前注册。

#### [x] import/photos 500 + 导入照片无人脸
**根因**：`/photos` 是 Docker `:ro` 只读挂载，写入报权限错误；文件未写入磁盘导致扫描不到人脸。  
**方案**：`_resolve_dest` 改写到 `/app/data/imported/`（可写 volume），docker-compose 新增对应挂载。

#### [x] face_min_photos 设置未生效（清理按钮硬编码 2）
**根因**：`People.vue` 的"清理"按钮硬编码 `prune(2)`，未读取设置页的阈值。  
**方案**：`onMounted` 从 `GET /api/v1/config` 读 `face_min_photos`，弹窗和 API 调用均使用该值。

#### [x] 打标并发数硬编码无法调整
**根因**：`run_batch_tagging(concurrency=2)` 写死，本地大模型单 GPU 并发会 OOM 或排队超时。  
**方案**：`app_config` 新增 `vlm_concurrency` 字段（默认 1），Settings.vue 打标区加"并发数"控件，`scan.py` 从配置读取后传给 tagger。

#### [x] VLM 打标全部失败（本地模型）
**根因（多个）**：
1. 部分本地模型不支持 `system` role（LM Studio 等）
2. 超时仅 30s，本地推理不够
3. JSON 提取逻辑弱，模型输出前缀/后缀导致解析失败
4. 失败原因不透明，只知道"失败 N 张"

**方案**：
- 合并 system prompt 到 user message（兼容所有本地模型）
- 超时改为 120s
- 用正则提取 `{...}` JSON 块
- `TaggingProgress` 新增 `last_failure` 字段，前端进度条下显示具体错误
- `scan.py` 允许 `api_key` 为空（本地模型无需 Key），只校验 `base_url` 非空

#### [x] 人脸识别 500+ 误识别人物
**根因**：DBSCAN 参数过松（eps=0.5，min_samples=1），单张误检人脸也会建立 Person。  
**方案**：
- 检测置信度阈值 0.5 → 0.7
- DBSCAN eps 0.5 → 0.4（更严格聚类）
- min_samples 1 → 2（至少 2 张才建人物）
- 新增 `POST /persons/prune?min_photos=N` 端点，识别完后自动按 `face_min_photos` 清理

---

### P1 — 核心功能

#### [x] 相册功能
已有 `Albums.vue`、`AlbumDetail.vue`、`SmartAlbums.vue` 三个完整页面。

#### [x] 人物合并 UI
`People.vue` 多选后底部 bar 已有"合并"按钮，弹出 Dialog 选择保留哪个人物。

#### [x] 重复照片批量删除
- 后端 `POST /photos/batch-delete`（最多 500 张软删除）
- Gallery 多选 bar 新增"移入回收站"按钮，删除后立即从本地 store 移除

---

### 已完成的其他功能

- [x] 视频文件支持（扫描、缩略图、HTTP 206 流式播放）
- [x] XMP 双向同步（DB↔XMP 冲突解析，mtime 裁决）
- [x] VLM 多模态批量打标（caption + tags，写回 XMP）
- [x] CLIP 语义搜索（numpy memmap 索引）
- [x] 人脸识别断点续传（face_analyzed_at 检查点）
- [x] 地理编码（离线 geonames.db，批量扫描 GPS 坐标）
- [x] 日记功能（月历视图、AI 生成草稿、封面图选择）
- [x] Gallery 媒体类型筛选（全部 / 照片 / 视频）
- [x] Gallery 已打标筛选（全部 / 已打标 / 未打标）+ 徽标显示
- [x] Places 地点扫描入口
- [x] 人物页空状态 + 识别进度恢复
- [x] Docker NAS 部署（自定义照片路径 `.env`）
- [x] nginx 上传限制 512MB
- [x] 多模型配置（ai_configs 表，支持激活切换）

---

## 📋 待办

### P2

- [ ] **已打标统计**：Settings 页显示"共 N 张，已打标 M 张"整体进度，让用户知道打标覆盖率
- [ ] **日记时间线视图**：目前只有月历，补充按时间顺序的列表/卡片视图
- [ ] **导入历史管理**：通过 `/import` 导入的照片缺少专属管理入口（查看、重命名批次等）

### P3

- [ ] **人脸识别参数暴露**：eps、det_score 等 DBSCAN 参数目前写死在代码里，改为设置页可调
- [ ] **照片地图视图**：照片已有 GPS 坐标，用 Leaflet 展示地图打点视图

### P4

- [ ] **CLIP 建索引进度反馈**：扫描时 CLIP 建索引无进度提示，用户不知道何时可以搜索

### P5

- [ ] **sqlite-vec 向量索引**：当前用 numpy memmap 全量扫描，十万量级以上才需要迁移到 sqlite-vec

---

*最后更新：2026-06-15*
