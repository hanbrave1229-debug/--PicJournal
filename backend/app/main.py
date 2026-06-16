"""
FastAPI application entry point.
"""
import subprocess
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.db.database import init_db
from app.api.v1 import router as api_v1_router

settings = get_settings()


def _check_db_not_on_network_mount() -> None:
    """
    如果 SQLite 数据库文件位于 NFS/SMB/CIFS 网络挂载路径上，
    WAL 模式会因为无法可靠地 mmap 共享内存文件 (.db-shm) 而导致
    死锁或静默数据损坏。检测到时打印高亮警告并退出进程。

    检测方案：读取 /proc/mounts（Linux），匹配 DB 所在路径的挂载点文件系统类型。
    非 Linux 环境（macOS 本地调试）静默跳过。
    """
    _NETWORK_FS = {"nfs", "nfs4", "nfs3", "cifs", "smb", "smbfs", "davfs", "fuse.sshfs"}

    # 从连接字符串中提取文件路径：sqlite+aiosqlite:////abs/path/db
    url = settings.database_url
    if "sqlite" not in url:
        return  # 非 SQLite 无需检测

    db_path_str = url.split("sqlite")[1].lstrip("+aiosqlite").lstrip(":")
    # 处理 sqlite:////app/data/db/photos.db → /app/data/db/photos.db
    db_path = Path(db_path_str.lstrip("/"))
    db_path = Path("/" + str(db_path))

    mounts_file = Path("/proc/mounts")
    if not mounts_file.exists():
        return  # macOS 或非 Linux，跳过

    try:
        mounts_text = mounts_file.read_text()
    except OSError:
        return

    # 找出所有网络挂载点，按路径深度降序（优先匹配最长前缀）
    network_mountpoints: list[Path] = []
    for line in mounts_text.splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        _device, mountpoint, fstype = parts[0], parts[1], parts[2]
        if fstype.lower().split(".")[0] in _NETWORK_FS or fstype.lower() in _NETWORK_FS:
            network_mountpoints.append(Path(mountpoint))

    network_mountpoints.sort(key=lambda p: len(p.parts), reverse=True)

    for mp in network_mountpoints:
        try:
            db_path.relative_to(mp)  # 如果成功，说明 db 在该网络挂载点下
        except ValueError:
            continue

        # ── 检测到危险配置，阻止启动 ─────────────────────────────────────────
        border = "=" * 70
        print(f"\n\033[1;31m{border}", file=sys.stderr)
        print("  ⚠️  危险：SQLite 数据库位于网络挂载路径！", file=sys.stderr)
        print(f"  数据库路径: {db_path}", file=sys.stderr)
        print(f"  网络挂载点: {mp}", file=sys.stderr)
        print("", file=sys.stderr)
        print("  在 NFS/SMB/CIFS 挂载卷上使用 WAL 模式的 SQLite 会因", file=sys.stderr)
        print("  无法可靠地 mmap .db-shm 共享内存文件而导致：", file=sys.stderr)
        print("  • 并发读写死锁（database is locked）", file=sys.stderr)
        print("  • .db-shm / .db-wal 元数据静默损坏", file=sys.stderr)
        print("", file=sys.stderr)
        print("  ✅ 正确做法：", file=sys.stderr)
        print("  1. 将 Docker volume 中的 DB 目录挂载到容器宿主机的 SSD 本地路径", file=sys.stderr)
        print("     例：volumes: - /opt/picjournal/db:/app/data/db", file=sys.stderr)
        print("  2. 照片原图目录可继续挂载到 NAS 网络共享磁盘", file=sys.stderr)
        print(f"{border}\033[0m\n", file=sys.stderr)
        sys.exit(1)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize DB tables on startup, then launch the periodic auto-scan loop."""
    import asyncio
    from app.services.scan_service import run_auto_scan_loop

    _check_db_not_on_network_mount()
    await init_db()

    auto_scan_task = asyncio.create_task(run_auto_scan_loop(), name="auto-scan-loop")
    try:
        yield
    finally:
        auto_scan_task.cancel()


app = FastAPI(
    title="Photo Manager API",
    version="1.0.0",
    description="Local intelligent photo analysis and management service",
    lifespan=lifespan,
)

# ── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Auth enforcement ───────────────────────────────────────────────────────────
# Every /api/v1/* route requires a valid JWT (header or cookie), except the
# auth bootstrap endpoints and API docs. JWT verification is stateless, so this
# middleware needs no DB access — it only checks the signature and expiry.
_AUTH_WHITELIST = {
    "/api/v1/auth/login",
    "/api/v1/auth/setup",
    "/api/v1/auth/setup-status",
    "/api/v1/auth/logout",
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
}


@app.middleware("http")
async def enforce_auth(request: Request, call_next):
    path = request.url.path
    # Let CORS preflight through; only guard the API namespace.
    if request.method == "OPTIONS" or not path.startswith("/api/v1/"):
        return await call_next(request)
    if path in _AUTH_WHITELIST:
        return await call_next(request)

    from app.core.auth_deps import extract_token
    from app.services import auth_service

    token = extract_token(request)
    if not token or auth_service.decode_token(token) is None:
        return JSONResponse(status_code=401, content={"detail": "未登录或登录已过期"})
    return await call_next(request)


# ── Routes ────────────────────────────────────────────────────────────────────
app.include_router(api_v1_router, prefix="/api/v1")


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["health"])
async def health_check() -> dict:
    return {"status": "ok"}
