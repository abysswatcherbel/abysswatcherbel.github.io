from __future__ import annotations

import argparse
import json
import os

from dotenv import load_dotenv

from util.maintenance import backfill_missing_streams, validate_season
from util.seasonal_schedule import SeasonScheduler


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill missing legal streaming links from r/anime Holo."
    )
    parser.add_argument("--year", type=int)
    parser.add_argument("--season", choices=("winter", "spring", "summer", "fall"))
    parser.add_argument(
        "--all",
        action="store_true",
        help="Refresh every show in the season instead of only null streams.",
    )
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

    summary = backfill_missing_streams(
        mongo_uri=os.environ["MONGO_URI"],
        year=year,
        season=season,
        overwrite=args.all,
        dry_run=args.dry_run,
        limit=args.limit,
        url_template=os.getenv("KARMA_HOLO_URL_TEMPLATE")
        or "https://raw.githubusercontent.com/r-anime/holo/master/season_configs/{season}_{year}.yaml",
    )
    print(json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
