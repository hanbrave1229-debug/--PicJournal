"""
Natural-language photo search — SQL-injection-safe rewrite.

POST /api/v1/search/nl
  body: { "query": "春天樱花", "limit": 30 }

Security architecture:
  LLM → strict JSON DSL → Pydantic whitelist validation → SQLAlchemy ORM query
  LLM output NEVER touches raw SQL text.
"""
from __future__ import annotations

import json
import logging
from typing import Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ValidationError, field_validator
from sqlalchemy import and_, or_
from sqlalchemy import select as sa_select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.photo import Photo
from app.schemas.photo import PhotoListResponse, PhotoResponse
from app.services.config_service import get_config

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Whitelist DSL schema ──────────────────────────────────────────────────────

# Only these columns may appear in LLM-generated filters.
_ALLOWED_FIELDS = {
    "ai_caption", "ai_tags", "camera_make", "camera_model",
    "city", "taken_at", "file_ext", "file_name",
}

_ALLOWED_OPS = {"contains", "not_contains", "eq", "neq", "gte", "lte", "gt", "lt"}

_FIELD_TO_COLUMN = {
    "ai_caption":   Photo.ai_caption,
    "ai_tags":      Photo.ai_tags,
    "camera_make":  Photo.camera_make,
    "camera_model": Photo.camera_model,
    "city":         Photo.city,
    "taken_at":     Photo.taken_at,
    "file_ext":     Photo.file_ext,
    "file_name":    Photo.file_name,
}


class SearchFilter(BaseModel):
    field: str
    operator: str
    value: str

    @field_validator("field")
    @classmethod
    def field_in_whitelist(cls, v: str) -> str:
        if v not in _ALLOWED_FIELDS:
            raise ValueError(f"Field '{v}' is not allowed")
        return v

    @field_validator("operator")
    @classmethod
    def op_in_whitelist(cls, v: str) -> str:
        if v not in _ALLOWED_OPS:
            raise ValueError(f"Operator '{v}' is not allowed")
        return v

    @field_validator("value")
    @classmethod
    def value_not_empty(cls, v: str) -> str:
        if not v or len(v) > 200:
            raise ValueError("value must be 1-200 chars")
        return v


class SearchDSL(BaseModel):
    filters: list[SearchFilter]
    logic: Literal["AND", "OR"] = "AND"


# ── Prompt ────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are a photo search assistant. Given a user query, output ONLY a valid JSON object matching this schema:

{
  "filters": [
    {"field": "<field>", "operator": "<op>", "value": "<value>"}
  ],
  "logic": "AND"  // or "OR"
}

Allowed fields: ai_caption, ai_tags, camera_make, camera_model, city, taken_at, file_ext, file_name
Allowed operators: contains, not_contains, eq, neq, gte, lte, gt, lt

Rules:
- Use "contains" for text search in ai_caption, ai_tags, city, camera_model etc.
- For dates use taken_at with gte/lte, value in ISO format "YYYY-MM-DD"
- For ai_tags use "contains" with a single keyword
- Output ONLY the JSON object, no explanation, no markdown fences
- If you cannot map the query to allowed fields, output: {"filters": [], "logic": "AND"}
"""


# ── LLM call ──────────────────────────────────────────────────────────────────

async def _nl_to_dsl(query: str, api_key: str, base_url: str, model: str) -> SearchDSL:
    url = (base_url.rstrip("/") if base_url else "https://api.openai.com/v1") + "/chat/completions"
    payload = {
        "model": model,
        "max_tokens": 512,
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

    # Parse and validate through Pydantic — if LLM output is malformed or uses
    # disallowed fields/operators, ValidationError is raised and caught by caller.
    try:
        parsed = json.loads(raw)
        return SearchDSL.model_validate(parsed)
    except (json.JSONDecodeError, ValidationError) as exc:
        logger.warning("LLM DSL parse failed: %s  raw=%r", exc, raw[:200])
        raise ValueError(f"LLM 返回格式不符合预期: {exc}") from exc


# ── DSL → SQLAlchemy conditions ────────────────────────────────────────────────

def _build_conditions(dsl: SearchDSL):
    """Convert validated DSL filters to SQLAlchemy column expressions."""
    conditions = [Photo.is_deleted.is_(False)]  # always enforced

    for f in dsl.filters:
        col = _FIELD_TO_COLUMN[f.field]
        op = f.operator
        val = f.value

        if op == "contains":
            conditions.append(col.ilike(f"%{val}%"))
        elif op == "not_contains":
            conditions.append(~col.ilike(f"%{val}%"))
        elif op == "eq":
            conditions.append(col == val)
        elif op == "neq":
            conditions.append(col != val)
        elif op == "gte":
            conditions.append(col >= val)
        elif op == "lte":
            conditions.append(col <= val)
        elif op == "gt":
            conditions.append(col > val)
        elif op == "lt":
            conditions.append(col < val)

    if dsl.logic == "OR" and len(dsl.filters) > 1:
        # Keep is_deleted guard in AND, wrap the rest in OR
        filter_conditions = conditions[1:]
        return [conditions[0], or_(*filter_conditions)]

    return conditions


# ── Request / response models ─────────────────────────────────────────────────

class NLSearchRequest(BaseModel):
    query: str
    limit: int = 30


class NLSearchResponse(BaseModel):
    query: str
    filters_applied: int
    total: int
    items: list[PhotoResponse]


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.post("/nl", response_model=NLSearchResponse, summary="Natural-language photo search")
async def nl_search(
    body: NLSearchRequest,
    db: AsyncSession = Depends(get_db),
) -> NLSearchResponse:
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

    # Step 1: NL → validated DSL (never raw SQL)
    try:
        dsl = await _nl_to_dsl(body.query, cfg.ai_api_key, base_url, model)
    except (httpx.HTTPStatusError, httpx.RequestError) as exc:
        logger.error("NL search LLM call failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"AI 接口请求失败: {exc}")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"AI 语义解析失败，请尝试简化关键词: {exc}")

    if not dsl.filters:
        raise HTTPException(status_code=422, detail="未能从查询中提取有效的搜索条件，请换个说法")

    logger.info("NL search DSL: %s", dsl.model_dump())

    # Step 2: build ORM query — no text() concatenation
    conditions = _build_conditions(dsl)
    stmt = (
        sa_select(Photo)
        .where(and_(*conditions))
        .order_by(Photo.taken_at.desc().nullslast())
        .limit(body.limit)
    )

    try:
        result = await db.execute(stmt)
        photos = list(result.scalars().all())
    except Exception as exc:
        logger.error("NL search ORM query failed: %s  dsl=%s", exc, dsl)
        raise HTTPException(status_code=500, detail="搜索执行出错，请重试")

    return NLSearchResponse(
        query=body.query,
        filters_applied=len(dsl.filters),
        total=len(photos),
        items=[PhotoResponse.from_orm(p) for p in photos],
    )
