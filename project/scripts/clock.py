#!/usr/bin/env python3
"""Leakage-proof as-of clock for ALPHA SWARM backtests.

search(as_of, records) returns only records with timestamp <= as_of.
Anything stamped after as_of is clipped. An explicit future_leak record
whose timestamp is after as_of raises LeakageError so leakage tests fail
loud rather than silently training on the future.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Optional


class LeakageError(Exception):
    """Raised when a future_leak record is presented at an earlier as_of."""


def parse_iso(value: Any) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if value is None:
        raise ValueError("timestamp is None")
    s = str(value).strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _record_ts(rec: Any) -> Optional[datetime]:
    if rec is None:
        return None
    if isinstance(rec, str):
        try:
            return parse_iso(rec)
        except (TypeError, ValueError):
            return None
    if not isinstance(rec, dict):
        return None
    for key in ("timestamp", "posted_at", "observed_at", "t", "ts", "at"):
        if rec.get(key) is not None:
            try:
                return parse_iso(rec[key])
            except (TypeError, ValueError):
                continue
    return None


def _is_future_leak_record(rec: Any) -> bool:
    if not isinstance(rec, dict):
        return False
    if rec.get("kind") == "future_leak":
        return True
    if rec.get("source_kind") == "future_leak":
        return True
    if rec.get("future_leak") is True:
        return True
    return False


def search(as_of: Any, records: Iterable[Any] | None) -> list:
    """Return records whose timestamp is <= as_of.

    Records with no timestamp are kept (they are treated as already known).
    Records with timestamp > as_of are clipped out.
    An explicit future_leak record after as_of raises LeakageError.
    """
    as_of_dt = parse_iso(as_of)
    if records is None:
        return []
    kept: list = []
    for rec in records:
        if rec is None:
            continue
        ts = _record_ts(rec)
        if _is_future_leak_record(rec):
            if ts is None or ts > as_of_dt:
                raise LeakageError(
                    f"future_leak record not visible at as_of={as_of_dt.isoformat()}"
                )
            # nested posts/tokens inside a leak wrapper
            nested = []
            if isinstance(rec.get("posts"), list):
                nested.extend(rec["posts"])
            if isinstance(rec.get("tokens"), list):
                nested.extend(rec["tokens"])
            for child in nested:
                child_ts = _record_ts(child)
                if child_ts is not None and child_ts > as_of_dt:
                    raise LeakageError(
                        "future_leak nested record after as_of"
                    )
        if ts is not None and ts > as_of_dt:
            continue
        kept.append(rec)
    return kept
