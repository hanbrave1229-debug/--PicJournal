"""
Memories API — auto-generated "On this day" highlights.

回忆功能：基于已有的 taken_at 自动挑出"那年今日"的照片，按年份分组。
后续可扩展：旅行回忆(按地点+时间聚类)、人物精选等。
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.photo import Photo
from app.schemas.photo import PhotoResponse

router = APIRouter()


@router.get("/on-this-day", summary="那年今日 — 历年同月同日的照片")
async def on_this_day(
    month: int | None = Query(None, ge=1, le=12, description="覆盖月份，默认今天"),
    day: int | None = Query(None, ge=1, le=31, description="覆盖日期，默认今天"),
    per_year: int = Query(30, ge=1, le=100, description="每年最多返回多少张"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Return photos taken on the same month/day in previous years, grouped by year
    (newest year first). Current year is excluded — these are *memories*.
    """
    today = date.today()
    mm = f"{month or today.month:02d}"
    dd = f"{day or today.day:02d}"
    cur_year = today.year

    # SQLite strftime on taken_at; only photos that actually have a taken_at.
    stmt = (
        select(Photo)
        .where(
            Photo.is_deleted.is_(False),
            Photo.is_archived.is_(False),
            Photo.taken_at.is_not(None),
            func.strftime("%m", Photo.taken_at) == mm,
            func.strftime("%d", Photo.taken_at) == dd,
            func.strftime("%Y", Photo.taken_at) != str(cur_year),
        )
        .order_by(Photo.taken_at.desc())
    )
    rows = (await db.execute(stmt)).scalars().all()

    # Group by year
    by_year: dict[int, list[Photo]] = {}
    for p in rows:
        y = p.taken_at.year
        by_year.setdefault(y, [])
        if len(by_year[y]) < per_year:
            by_year[y].append(p)

    groups = [
        {
            "year": y,
            "years_ago": cur_year - y,
            "count": len(by_year[y]),
            "photos": [PhotoResponse.from_orm(p) for p in by_year[y]],
        }
        for y in sorted(by_year.keys(), reverse=True)
    ]

    return {
        "date": f"{mm}-{dd}",
        "total": len(rows),
        "groups": groups,
    }


@router.get("/cards", summary="回忆卡片汇总(首页用)")
async def memory_cards(db: AsyncSession = Depends(get_db)) -> dict:
    """
    Lightweight summary for the home page: how many "on this day" memories exist
    and a cover thumbnail, so the UI can show an entry card without loading all.
    """
    today = date.today()
    mm = f"{today.month:02d}"
    dd = f"{today.day:02d}"

    stmt = (
        select(Photo)
        .where(
            Photo.is_deleted.is_(False),
            Photo.is_archived.is_(False),
            Photo.taken_at.is_not(None),
            func.strftime("%m", Photo.taken_at) == mm,
            func.strftime("%d", Photo.taken_at) == dd,
            func.strftime("%Y", Photo.taken_at) != str(today.year),
        )
        .order_by(Photo.taken_at.desc())
    )
    rows = (await db.execute(stmt)).scalars().all()

    years = sorted({p.taken_at.year for p in rows}, reverse=True)
    cover = rows[0] if rows else None

    return {
        "on_this_day": {
            "date": f"{mm}-{dd}",
            "count": len(rows),
            "years": years,
            "cover_id": cover.id if cover else None,
        }
    }
