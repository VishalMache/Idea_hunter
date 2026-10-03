"""Manual import adapter for sources without a compliant automated interface."""
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Iterator
from idea_hunter.collectors.base import RawObservation
from idea_hunter.collectors.source_catalog import get_source


def _date(value):
    if not value: return None
    try: return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError: return None


def iter_manual_observations(source_key: str, path: str | Path, topic: str = "") -> Iterator[RawObservation]:
    """Read a user-provided JSON array or CSV export into the canonical contract.

    Expected portable fields: text/content/description, url, title, author/company,
    published_at/date, engagement/upvotes, and any additional columns as metadata.
    """
    definition = get_source(source_key)
    file_path = Path(path)
    if file_path.suffix.lower() == ".json":
        payload = json.loads(file_path.read_text(encoding="utf-8"))
        if not isinstance(payload, list): raise ValueError("Manual JSON import must contain an array of records.")
        rows = payload
    elif file_path.suffix.lower() == ".csv":
        with file_path.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
    else:
        raise ValueError("Manual imports support only .json and .csv files.")
    for row in rows:
        if not isinstance(row, dict): continue
        text = row.get("text") or row.get("content") or row.get("description") or row.get("review") or ""
        title = row.get("title") or row.get("product") or row.get("company") or ""
        raw_text = f"{title}\n{text}".strip()
        if not raw_text: continue
        try: engagement = int(row.get("engagement") or row.get("upvotes") or row.get("rating_count") or 0)
        except (TypeError, ValueError): engagement = 0
        yield RawObservation(source_type=source_key, source_url=row.get("url") or row.get("source_url"), raw_text=raw_text,
            author=row.get("author") or row.get("company") or row.get("product"), published_at=_date(row.get("published_at") or row.get("date")),
            engagement=engagement, topic=topic, metadata={"title": title, "source_categories": definition.categories,
            "signal_kind": definition.signal_kind, "imported": True, "source_record": row})
