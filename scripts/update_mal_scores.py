from __future__ import annotations

import argparse
import json
import os

from dotenv import load_dotenv

from util.maintenance import update_mal_scores, validate_season
from util.seasonal_schedule import SeasonScheduler


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Refresh MAL scores for one anime season."
    )
    parser.add_argument("--year", type=int)
    parser.add_argument("--season", choices=("winter", "spring", "summer", "fall"))
    parser.add_argument(
        "--week",
        type=int,
        help="Also attach the fresh MAL snapshot to episodes from this ranking week.",
    )
    parser.add_argument("--missing-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int)
    return parser.parse_args()


def main() -> int:
    load_dotenv()
    args = parse_args()
    schedule = SeasonScheduler(schedule_type="post")
    year = args.year or schedule.year
    season = args.season or schedule.season_name
    if year is None or season is None:
        raise RuntimeError("Could not determine year and season")
    year, season = validate_season(year, season)
    week = args.week
    if args.year is None and args.season is None and week is None:
        week = schedule.week_id

    mode = "dry run" if args.dry_run else "database update"
    week_text = f", week {week}" if week is not None else ""
    print(
        f"Starting MAL score {mode} for {season} {year}{week_text}...",
        flush=True,
    )
    summary = update_mal_scores(
        mongo_uri=os.environ["MONGO_URI"],
        mal_client_id=os.getenv("MAL_SECRET", ""),
        year=year,
        season=season,
        week=week,
        missing_only=args.missing_only,
        dry_run=args.dry_run,
        limit=args.limit,
        progress=lambda message: print(message, flush=True),
    )
    print("MAL score update finished.", flush=True)
    print(json.dumps(summary, indent=2, default=str))
    return 1 if summary["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
