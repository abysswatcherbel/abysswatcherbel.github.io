from __future__ import annotations

import re
from datetime import datetime, timezone
from statistics import median
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


def estimate_hour_48_karma(
    *,
    snapshot_karma: int,
    growth_ratios: Iterable[float],
    current_karma: int | None = None,
) -> tuple[int, float, int]:
    """Estimate hour-48 karma with the median historical growth multiplier."""
    ratios = [float(value) for value in growth_ratios if float(value) > 0]
    if not ratios:
        raise ValueError("no historical hour-48 growth data is available")

    multiplier = float(median(ratios))
    estimate = max(0, round(int(snapshot_karma) * multiplier))
    if current_karma is not None:
        # A later observed Reddit score is a useful upper bound for the estimate.
        upper_bound = max(int(snapshot_karma), int(current_karma))
        estimate = min(estimate, upper_bound)
    estimate = max(int(snapshot_karma), estimate)
    return estimate, multiplier, len(ratios)


def build_episode_record(
    post: dict[str, Any], *, force: bool = False
) -> dict[str, Any]:
    """Build the nested seasonal entry used by the normal 48-hour finalizer."""
    required = ("reddit_id", "episode", "url", "comments", "upvote_ratio")
    missing = [name for name in required if post.get(name) is None]
    if missing:
        raise ValueError(f"missing repair fields: {', '.join(missing)}")
    snapshot_karma = post.get("expected_karma")
    snapshot_hour = post.get("expected_karma_hour")
    exact_snapshot = snapshot_karma is not None and float(snapshot_hour or 0) == 48

    if exact_snapshot:
        karma = snapshot_karma
        estimated = False
        karma_source = "hour_48_snapshot"
    elif force and post.get("estimated_48h_karma") is not None:
        karma = post["estimated_48h_karma"]
        estimated = True
        karma_source = "historical_median_curve"
    elif force and snapshot_karma is not None:
        karma = snapshot_karma
        estimated = True
        karma_source = "latest_hourly_snapshot"
    elif force and post.get("current_karma") is not None:
        karma = post["current_karma"]
        estimated = True
        karma_source = "reddit_current"
        snapshot_hour = None
    elif snapshot_karma is None:
        raise ValueError("no tracked karma snapshot is available")
    else:
        raise ValueError("hour-48 karma snapshot is not available")

    record = {
        "week_id": int(post["week_id"]),
        "episode": str(post["episode"]),
        "karma": int(karma),
        "comments": int(post["comments"]),
        "upvote_ratio": float(post["upvote_ratio"]),
        "reddit_id": str(post["reddit_id"]),
        "url": str(post["url"]),
    }
    if estimated:
        estimate_details = {
            "karma_estimated": True,
            "karma_snapshot_hour": snapshot_hour,
            "karma_source": karma_source,
        }
        if post.get("karma_estimation_multiplier") is not None:
            estimate_details["karma_estimation_multiplier"] = post[
                "karma_estimation_multiplier"
            ]
        if post.get("karma_estimation_sample_size") is not None:
            estimate_details["karma_estimation_sample_size"] = post[
                "karma_estimation_sample_size"
            ]
        record.update(estimate_details)
    return record


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
        expected_karma_hour = None
        if watch:
            snapshots = watch.get("hourly_karma") or []
            at_48_hours = [item for item in snapshots if item.get("hour") == 48]
            if at_48_hours:
                expected_karma = at_48_hours[-1].get("karma")
                expected_karma_hour = at_48_hours[-1].get("hour")
            elif snapshots:
                latest = max(
                    snapshots, key=lambda item: float(item.get("hour", 0))
                )
                expected_karma = latest.get("karma")
                expected_karma_hour = latest.get("hour")

        results.append(
            {
                **post,
                "age_hours": round(age_hours, 1),
                "tracked": watch is not None,
                "expected_karma": expected_karma,
                "expected_karma_hour": expected_karma_hour,
                "status": status,
            }
        )

    return results

