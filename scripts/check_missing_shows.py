from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from dotenv import load_dotenv
from praw import Reddit
from pymongo import MongoClient

from util.maintenance import extract_mal_id, validate_season
from util.missing_shows import (
    audit_reddit_posts,
    build_episode_record,
    estimate_hour_48_karma,
    extract_episode,
    extract_reddit_post_id,
    is_rankable_episode,
)
from util.seasonal_schedule import SeasonScheduler


SEASON_NUMBERS = {"winter": 1, "spring": 2, "summer": 3, "fall": 4}
MISSING_STATUSES = {"missing_finalization", "missing_untracked"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare r/anime episode discussions with hourly tracking and finalized "
            "seasonal ranking records. This command is read-only unless --fix or "
            "--fix-force is used."
        )
    )
    parser.add_argument("--year", type=int)
    parser.add_argument("--season", choices=tuple(SEASON_NUMBERS))
    parser.add_argument("--week", type=int, choices=range(1, 14))
    parser.add_argument(
        "--post",
        help="Check one Reddit post URL or ID instead of a whole ranking week.",
    )
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument(
        "--include-ok",
        action="store_true",
        help="Print finalized and pending posts as well as missing posts.",
    )
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument(
        "--fix",
        action="store_true",
        help=(
            "Insert missing finalized posts using their tracked hour-48 karma. "
            "Posts without a complete snapshot are skipped."
        ),
    )
    parser.add_argument(
        "--fix-force",
        action="store_true",
        help=(
            "Repair even without an exact hour-48 snapshot, marking karma as "
            "estimated and using the latest snapshot or current Reddit score."
        ),
    )
    return parser.parse_args()


def reddit_client() -> Reddit:
    required = ("REDDIT_ID", "REDDIT_SECRET", "REDDIT_USERNAME")
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError(f"Missing Reddit settings: {', '.join(missing)}")
    return Reddit(
        client_id=os.environ["REDDIT_ID"],
        client_secret=os.environ["REDDIT_SECRET"],
        user_agent=os.environ["REDDIT_USERNAME"],
    )


def post_details(submission: Any) -> dict[str, Any] | None:
    if not is_rankable_episode(submission.title):
        return None
    return {
        "reddit_id": submission.id,
        "mal_id": extract_mal_id(submission.selftext),
        "title": submission.title,
        "episode": extract_episode(submission.title),
        "created_utc": int(submission.created_utc),
        "url": f"https://www.reddit.com{submission.permalink}",
        "comments": int(submission.num_comments),
        "upvote_ratio": float(submission.upvote_ratio),
        "current_karma": int(submission.score),
    }


def resolve_scope(args: argparse.Namespace) -> tuple[int, str, int, Any]:
    publication_schedule = SeasonScheduler(schedule_type="post")
    year = args.year or publication_schedule.year
    season = args.season or publication_schedule.season_name
    week = args.week or publication_schedule.week_id
    if year is None or season is None or week is None:
        raise RuntimeError("Could not determine the ranking week")
    year, season = validate_season(year, season)
    episode_schedule = SeasonScheduler(schedule_type="episodes")
    details = episode_schedule.get_schedule_for_date(
        year=year,
        season=SEASON_NUMBERS[season],
        week_id=week,
    )
    if details is None or details.start_date is None or details.end_date is None:
        raise RuntimeError(f"No post schedule found for {season} {year}, week {week}")
    return year, season, week, details


def fetch_posts(
    reddit: Reddit, args: argparse.Namespace
) -> tuple[list[dict[str, Any]], int, str, int]:
    if args.post:
        submission = reddit.submission(id=extract_reddit_post_id(args.post))
        details = post_details(submission)
        if details is None:
            raise RuntimeError("The supplied post is not a rankable episode discussion")
        schedule = SeasonScheduler(
            schedule_type="episodes",
            post_time=datetime.fromtimestamp(submission.created_utc, timezone.utc),
        )
        if schedule.year is None or schedule.season_name is None or schedule.week_id is None:
            raise RuntimeError("Could not determine the supplied post's ranking week")
        return [details], schedule.year, schedule.season_name, schedule.week_id

    year, season, week, window = resolve_scope(args)
    print(
        f"Fetching AutoLovepon posts for {season} {year}, week {week} "
        f"({window.start_date:%Y-%m-%d} to {window.end_date:%Y-%m-%d})...",
        flush=True,
    )
    posts = []
    for submission in reddit.redditor("AutoLovepon").submissions.new(limit=args.limit):
        created_at = datetime.fromtimestamp(submission.created_utc, timezone.utc)
        if window.start_date <= created_at <= window.end_date:
            details = post_details(submission)
            if details is not None:
                posts.append(details)
    return posts, year, season, week


def repair_missing_posts(
    mongo_uri: str,
    *,
    year: int,
    season: str,
    week: int,
    missing: list[dict[str, Any]],
    force: bool = False,
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "attempted": len(missing),
        "fixed": 0,
        "already_finalized": 0,
        "estimated": 0,
        "skipped": [],
    }
    path = f"reddit_karma.{year}.{season}"
    client = MongoClient(mongo_uri)
    try:
        collection = client.anime.seasonals
        watch_collection = client.anime.karma_watch
        growth_ratio_cache: dict[float, list[float]] = {}
        for post in missing:
            reddit_id = str(post["reddit_id"])
            mal_id = post.get("mal_id")
            if mal_id is None:
                reason = "Reddit post has no MAL ID"
                summary["skipped"].append({"reddit_id": reddit_id, "reason": reason})
                print(f"SKIPPED {reddit_id}: {reason}", flush=True)
                continue

            repair_post = {**post, "week_id": week}
            snapshot_hour = post.get("expected_karma_hour")
            snapshot_karma = post.get("expected_karma")
            if (
                force
                and snapshot_karma is not None
                and snapshot_hour is not None
                and float(snapshot_hour or 0) != 48
            ):
                hour = float(snapshot_hour)
                if hour not in growth_ratio_cache:
                    ratios = []
                    history_query = {
                        "year": year,
                        "season": season,
                        "hourly_karma": {
                            "$all": [
                                {"$elemMatch": {"hour": hour}},
                                {"$elemMatch": {"hour": 48.0}},
                            ]
                        },
                    }
                    for history in watch_collection.find(
                        history_query, {"_id": 0, "hourly_karma": 1}
                    ):
                        values = {
                            float(item.get("hour")): item.get("karma")
                            for item in history.get("hourly_karma", [])
                        }
                        at_snapshot = values.get(hour)
                        at_48 = values.get(48.0)
                        if (
                            at_snapshot is not None
                            and at_snapshot > 0
                            and at_48 is not None
                        ):
                            ratios.append(at_48 / at_snapshot)
                    growth_ratio_cache[hour] = ratios

                try:
                    estimate, multiplier, sample_size = estimate_hour_48_karma(
                        snapshot_karma=int(snapshot_karma),
                        growth_ratios=growth_ratio_cache[hour],
                        current_karma=post.get("current_karma"),
                    )
                    repair_post.update(
                        {
                            "estimated_48h_karma": estimate,
                            "karma_estimation_multiplier": round(multiplier, 4),
                            "karma_estimation_sample_size": sample_size,
                        }
                    )
                except ValueError:
                    # build_episode_record retains its explicit latest/current fallback.
                    pass
            try:
                episode_record = build_episode_record(repair_post, force=force)
            except (TypeError, ValueError) as error:
                summary["skipped"].append(
                    {"reddit_id": reddit_id, "reason": str(error)}
                )
                print(f"SKIPPED {reddit_id}: {error}", flush=True)
                continue

            result = collection.update_one(
                {
                    "id": int(mal_id),
                    f"{path}.reddit_id": {"$ne": reddit_id},
                },
                {"$push": {path: episode_record}},
            )
            if result.modified_count:
                summary["fixed"] += 1
                if episode_record.get("karma_estimated"):
                    summary["estimated"] += 1
                estimate = " estimated" if episode_record.get("karma_estimated") else ""
                snapshot = episode_record.get("karma_snapshot_hour")
                source = episode_record.get("karma_source")
                multiplier = episode_record.get("karma_estimation_multiplier")
                provenance = (
                    f", source={source}"
                    + (f", snapshot_hour={snapshot}" if snapshot is not None else "")
                    + (f", multiplier={multiplier}" if multiplier is not None else "")
                    if estimate
                    else ""
                )
                print(
                    f"FIXED {reddit_id}: {post['title']} "
                    f"(karma={episode_record['karma']}{estimate}{provenance})",
                    flush=True,
                )
            elif collection.count_documents(
                {"id": int(mal_id), f"{path}.reddit_id": reddit_id}, limit=1
            ):
                summary["already_finalized"] += 1
                print(f"ALREADY FINALIZED {reddit_id}", flush=True)
            else:
                reason = f"MAL {mal_id} is not present in seasonals"
                summary["skipped"].append({"reddit_id": reddit_id, "reason": reason})
                print(f"SKIPPED {reddit_id}: {reason}", flush=True)
    finally:
        client.close()
    return summary


def database_state(
    mongo_uri: str,
    *,
    year: int,
    season: str,
    reddit_ids: list[str],
) -> tuple[set[str], dict[str, dict[str, Any]]]:
    client = MongoClient(mongo_uri)
    try:
        db = client.anime
        path = f"reddit_karma.{year}.{season}.reddit_id"
        finalized = {
            str(value)
            for value in db.seasonals.distinct(path, {path: {"$in": reddit_ids}})
        }
        watch_entries = {
            str(entry["reddit_id"]): entry
            for entry in db.karma_watch.find(
                {"reddit_id": {"$in": reddit_ids}},
                {"_id": 0, "reddit_id": 1, "hourly_karma": 1},
            )
        }
        return finalized, watch_entries
    finally:
        client.close()


def main() -> int:
    load_dotenv()
    args = parse_args()
    posts, year, season, week = fetch_posts(reddit_client(), args)
    reddit_ids = [post["reddit_id"] for post in posts]
    print(f"Found {len(posts)} rankable episode discussion(s).", flush=True)

    finalized, watch_entries = database_state(
        os.environ["MONGO_URI"],
        year=year,
        season=season,
        reddit_ids=reddit_ids,
    )
    results = audit_reddit_posts(
        posts,
        finalized_ids=finalized,
        watch_entries=watch_entries,
    )
    counts = Counter(result["status"] for result in results)
    missing = [result for result in results if result["status"] in MISSING_STATUSES]

    fix_summary = None
    if args.fix_force:
        print(
            "FORCE MODE: non-48-hour karma values will be stored as estimates.",
            flush=True,
        )
    if (args.fix or args.fix_force) and missing:
        print(f"Repairing {len(missing)} missing post(s)...", flush=True)
        fix_summary = repair_missing_posts(
            os.environ["MONGO_URI"],
            year=year,
            season=season,
            week=week,
            missing=missing,
            force=args.fix_force,
        )
        finalized, watch_entries = database_state(
            os.environ["MONGO_URI"],
            year=year,
            season=season,
            reddit_ids=reddit_ids,
        )
        results = audit_reddit_posts(
            posts,
            finalized_ids=finalized,
            watch_entries=watch_entries,
        )
        counts = Counter(result["status"] for result in results)
        missing = [
            result for result in results if result["status"] in MISSING_STATUSES
        ]

    report = {
        "year": year,
        "season": season,
        "week": week,
        "checked": len(results),
        "counts": dict(sorted(counts.items())),
        "missing": missing,
    }
    if fix_summary is not None:
        report["fix"] = fix_summary
    if args.as_json:
        if args.include_ok:
            report["posts"] = results
        print(json.dumps(report, indent=2, default=str))
    else:
        visible = results if args.include_ok else missing
        for result in visible:
            karma = ""
            if result["expected_karma"] is not None:
                snapshot_hour = result.get("expected_karma_hour")
                if float(snapshot_hour or 0) == 48:
                    karma = f", hour-48 karma {result['expected_karma']}"
                else:
                    karma = (
                        f", latest karma {result['expected_karma']} "
                        f"at hour {snapshot_hour}"
                    )
            print(
                f"{result['status'].upper()}: {result['title']} "
                f"[{result['reddit_id']}, {result['age_hours']}h old{karma}]"
            )
            print(f"  {result['url']}")
        print(
            f"Summary: checked={len(results)}, missing={len(missing)}, "
            + ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))
        )
        if fix_summary is not None:
            print(
                "Fix summary: "
                f"attempted={fix_summary['attempted']}, "
                f"fixed={fix_summary['fixed']}, "
                f"estimated={fix_summary['estimated']}, "
                f"already_finalized={fix_summary['already_finalized']}, "
                f"skipped={len(fix_summary['skipped'])}"
            )
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())

