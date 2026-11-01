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
            "seasonal ranking records. This command is read-only."
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

    report = {
        "year": year,
        "season": season,
        "week": week,
        "checked": len(results),
        "counts": dict(sorted(counts.items())),
        "missing": missing,
    }
    if args.as_json:
        if args.include_ok:
            report["posts"] = results
        print(json.dumps(report, indent=2, default=str))
    else:
        visible = results if args.include_ok else missing
        for result in visible:
            karma = (
                f", expected karma {result['expected_karma']}"
                if result["expected_karma"] is not None
                else ""
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
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())

