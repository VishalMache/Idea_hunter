"""Canonical ingestion helpers shared by source adapters."""

import hashlib
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from idea_hunter.db.models import SourceQuery


def normalized_content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def source_query_key(query: str, config: dict | None = None) -> str:
    payload = f"{query.strip().casefold()}|{sorted((config or {}).items())}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:48]


async def get_or_create_source_query(
    session: AsyncSession,
    *,
    source_id: int,
    query: str,
    config: dict | None = None,
) -> SourceQuery:
    key = source_query_key(query, config)
    result = await session.scalar(
        select(SourceQuery).where(SourceQuery.source_id == source_id, SourceQuery.query_key == key)
    )
    if result:
        return result
    result = SourceQuery(
        source_id=source_id,
        query_key=key,
        query_text=query,
        config_json=config or {},
    )
    session.add(result)
    await session.flush()
    return result


def mark_source_query_success(query: SourceQuery, cursor: str | None = None) -> None:
    query.last_success_at = datetime.now(timezone.utc)
    query.last_error = None
    if cursor:
        query.last_seen_cursor = cursor


def mark_source_query_error(query: SourceQuery, error: Exception) -> None:
    query.last_error = str(error)[:4000]
