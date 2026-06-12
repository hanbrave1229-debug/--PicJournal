"""
Natural-language photo search.

POST /api/v1/search/nl
  body: { "query": "春天樱花", "limit": 30 }

Flow:
  1. Send query to LLM → get a safe SQL WHERE clause fragment.
  2. Execute  SELECT … FROM photos WHERE <fragment>  against SQLite.
  3. Return matching PhotoResponse list.

The LLM is constrained to output ONLY a WHERE clause (no SELECT/FROM/DROP/etc.)
and is given the exact column list so it can construct correct queries.
"""
from __future__ import annotations

import json
import logging
import re

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.photo import PhotoListResponse, PhotoResponse
from app.services.config_service import get_config

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Prompt ────────────────────────────────────────────────────────────────────

_SCHEMA_DESC = """
Table: photos
Columns:
  id            INTEGER   -- primary key
  file_name     TEXT      -- e.g. "IMG_0042.jpg"
  file_ext      TEXT      -- e.g. ".jpg"
  file_size     INTEGER   -- bytes
  width         INTEGER
  height        INTEGER
  taken_at      DATETIME  -- ISO string "2024-03-15 14:22:00", nullable
  camera_make   TEXT      -- e.g. "Apple", nullable
  camera_model  TEXT      -- e.g. "iPhone 15 Pro", nullable
  iso           INTEGER   -- nullable
  ai_caption    TEXT      -- Chinese scene description, nullable
  ai_tags       TEXT      -- JSON array of Chinese keywords, e.g. '["樱花","春天"]', nullable
  is_deleted    INTEGER   -- 0 = active, 1 = deleted
"""

_SYSTEM_PROMPT = (
    "You are a SQLite query assistant. "
    "Given a user search query, output ONLY a valid SQLite WHERE clause (no SELECT, FROM, semicolons, or SQL comments). "
    "Use only the columns listed below. "
    "For ai_tags (stored as JSON array text), use: json_each(ai_tags) in a subquery, e.g. "
    "id IN (SELECT p2.id FROM photos p2, json_each(p2.ai_tags) t WHERE t.value LIKE '%keyword%'). "
    "Always include: is_deleted = 0. "
    "Output only the WHERE clause body (the part after WHERE), nothing else.\n\n"
    + _SCHEMA_DESC
)


# ── Safety guard ──────────────────────────────────────────────────────────────

_FORBIDDEN_PATTERN = re.compile(
    r"\b(DROP|DELETE|INSERT|UPDATE|ALTER|CREATE|ATTACH|DETACH|PRAGMA|TRUNCATE|REPLACE)\b",
    re.IGNORECASE,
)


def _is_safe_where(clause: str) -> bool:
    """Reject clauses that contain DML or DDL keywords."""
    return not _FORBIDDEN_PATTERN.search(clause)


# ── LLM call ──────────────────────────────────────────────────────────────────

async def _nl_to_where(query: str, api_key: str, base_url: str, model: str) -> str:
    """Ask the LLM to convert *query* to a SQL WHERE clause fragment."""
    url = (base_url.rstrip("/") if base_url else "https://api.openai.com/v1") + "/chat/completions"
    payload = {
        "model": model,
        "max_tokens": 256,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": f"Search query: {query}"},
        ],
    }
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
        )
    resp.raise_for_status()
    raw: str = resp.json()["choices"][0]["message"]["content"].strip()
    # Strip markdown fences if model wraps in ```sql ... ```
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"```$", "", raw).strip()
    return raw


# ── Request / response models ─────────────────────────────────────────────────

class NLSearchRequest(BaseModel):
    query: str
    limit: int = 30


class NLSearchResponse(BaseModel):
    query: str
    where_clause: str
    total: int
    items: list[PhotoResponse]


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.post("/nl", response_model=NLSearchResponse, summary="Natural-language photo search")
async def nl_search(
    body: NLSearchRequest,
    db: AsyncSession = Depends(get_db),
) -> NLSearchResponse:
    """
    Convert a natural-language query to SQL and return matching photos.

    Requires AI API key to be configured in Settings.
    """
    if not body.query.strip():
        raise HTTPException(status_code=400, detail="查询内容不能为空")
    if body.limit < 1 or body.limit > 200:
        raise HTTPException(status_code=400, detail="limit 需在 1–200 之间")

    cfg = await get_config(db)
    if not cfg.ai_api_key:
        raise HTTPException(
            status_code=400,
            detail="AI API Key 未配置，请前往「智能设置」完成配置后再使用自然语言搜索",
        )

    model    = cfg.ai_model or "gpt-4o-mini"
    base_url = cfg.ai_base_url or ""

    # Step 1: NL → WHERE
    try:
        where_clause = await _nl_to_where(body.query, cfg.ai_api_key, base_url, model)
    except (httpx.HTTPStatusError, httpx.RequestError) as exc:
        logger.error("NL search LLM call failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"AI 接口请求失败: {exc}")

    if not where_clause or not _is_safe_where(where_clause):
        raise HTTPException(status_code=422, detail="AI 返回了不安全的查询，已拒绝执行")

    # Step 2: execute
    sql = text(
        f"SELECT id FROM photos WHERE {where_clause} "
        f"ORDER BY taken_at DESC NULLS LAST LIMIT :limit"
    )
    try:
        result = await db.execute(sql, {"limit": body.limit})
        photo_ids: list[int] = [row[0] for row in result.fetchall()]
    except Exception as exc:
        logger.error("NL search SQL error. clause=%r  err=%s", where_clause, exc)
        raise HTTPException(status_code=422, detail=f"生成的查询无法执行，请换个说法重试: {exc}")

    # Step 3: fetch full Photo ORM objects for the matched IDs
    if not photo_ids:
        return NLSearchResponse(
            query=body.query, where_clause=where_clause, total=0, items=[]
        )

    from sqlalchemy import select as sa_select
    from app.models.photo import Photo

    rows = await db.execute(
        sa_select(Photo)
        .where(Photo.id.in_(photo_ids))
        .order_by(Photo.taken_at.desc().nullslast())
    )
    photos = list(rows.scalars().all())

    return NLSearchResponse(
        query=body.query,
        where_clause=where_clause,
        total=len(photos),
        items=[PhotoResponse.from_orm(p) for p in photos],
    )
