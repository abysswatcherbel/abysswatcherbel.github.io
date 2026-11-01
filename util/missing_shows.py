from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable


POST_ID_PATTERN = re.compile(r"(?:comments/)?([a-z0-9]{5,10})(?:/|$)", re.IGNORECASE)
EPISODE_PATTERN = re.compile(
    r"(?:-|,)\s+Episodes?\s+([0-9]+(?:\.[0-9]+)?)\s+discussion\b",
    re.IGNORECASE,
)


def extract_reddit_post_id(value: str) -> str:
    candidate = value.strip().rstrip("/")
    if "/comments/" not in candidate:
        if re.fullmatch(r"[a-z0-9]{5,10}", candidate, re.IGNORECASE):
            return candidate.lower()
        raise ValueError(f"Could not extract a Reddit post ID from: {value}")
    match = POST_ID_PATTERN.search(candidate.split("/comments/", 1)[1])
    if not match:
        raise ValueError(f"Could not extract a Reddit post ID from: {value}")
    return match.group(1).lower()


def extract_episode(title: str) -> str | None:
    match = EPISODE_PATTERN.search(title)
    return match.group(1) if match else None


def is_rankable_episode(title: str) -> bool:
    """Return whether a post is an episode discussion that should enter the rank."""
    episode = extract_episode(title)
    return episode is not None and float(episode) != 0


def audit_reddit_posts(
    posts: Iterable[dict[str, Any]],
    *,
    finalized_ids: set[str],
    watch_entries: dict[str, dict[str, Any]],
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    current_time = now or datetime.now(timezone.utc)
    results: list[dict[str, Any]] = []

    for post in posts:
        reddit_id = str(post["reddit_id"])
        created_at = datetime.fromtimestamp(float(post["created_utc"]), timezone.utc)
        age_hours = (current_time - created_at).total_seconds() / 3600
        watch = watch_entries.get(reddit_id)

        if reddit_id in finalized_ids:
            status = "finalized"
        elif age_hours < 48:
            status = "pending" if watch else "pending_untracked"
        else:
            status = "missing_finalization" if watch else "missing_untracked"

        expected_karma = None
        if watch:
            snapshots = watch.get("hourly_karma") or []
            at_48_hours = [item for item in snapshots if item.get("hour") == 48]
            if at_48_hours:
                expected_karma = at_48_hours[-1].get("karma")
            elif snapshots:
                expected_karma = max(
                    snapshots, key=lambda item: float(item.get("hour", 0))
                ).get("karma")

        results.append(
            {
                **post,
                "age_hours": round(age_hours, 1),
                "tracked": watch is not None,
                "expected_karma": expected_karma,
                "status": status,
            }
        )

    return results

