#!/usr/bin/env python
"""
Backup script for generating weekly ranking JSON files.

This script extracts weekly ranking data from MongoDB and stores it in the static/data directory
as JSON files. This allows the historical ranking data to be served as static files on GitHub Pages.

Usage:
  python backup_rankings.py          # Backup all years and seasons
  python backup_rankings.py 2025     # Backup specific year
  python backup_rankings.py 2025 winter  # Backup specific year and season
"""

import os
import sys
from dotenv import load_dotenv
from util.data_backup import backup_weekly_rankings, get_available_seasons_from_db
from util.logger_config import logger


def main():
    load_dotenv()

    # Parse command line arguments
    year = None
    season = None

    if len(sys.argv) > 1:
        year = sys.argv[1]

    if len(sys.argv) > 2:
        season = sys.argv[2].lower()
        if season not in ["winter", "spring", "summer", "fall"]:
            print(
                f"Invalid season: {season}. Must be one of: winter, spring, summer, fall"
            )
            return

    # Get available seasons before starting backup
    available_seasons = get_available_seasons_from_db()

    if year and year not in available_seasons:
        print(f"Year {year} not found in the database")
        print(f"Available years: {', '.join(available_seasons.keys())}")
        return

    if year and season and season not in available_seasons.get(year, {}):
        print(f"Season {season} not found for year {year}")
        print(
            f"Available seasons for {year}: {', '.join(available_seasons[year].keys())}"
        )
        return

    # Print information about what we're backing up
    if year and season:
        print(f"Backing up data for {year} {season}")
        week_info = available_seasons[year][season]
        print(f"Found weeks: {', '.join(str(w) for w in week_info)}")
    elif year:
        print(f"Backing up all seasons for {year}")
        for s, weeks in available_seasons[year].items():
            print(f"- {s}: weeks {', '.join(str(w) for w in weeks)}")
    else:
        print("Backing up all available data")
        for y, seasons in available_seasons.items():
            print(f"{y}:")
            for s, weeks in seasons.items():
                print(f"- {s}: weeks {', '.join(str(w) for w in weeks)}")

    # Run the backup
    result = backup_weekly_rankings(specific_year=year, specific_season=season)

    # Print summary
    if result["success"]:
        print(f"\nBackup completed successfully!")
        print(f"- Years processed: {result['years_processed']}")
        print(f"- Seasons processed: {result['seasons_processed']}")
        print(f"- Weeks processed: {result['weeks_processed']}")
    else:
        print(f"\nBackup completed with errors:")
        for error in result["errors"]:
            print(f"- {error}")

    print("\nWeekly ranking data is now available at:")
    print("static/data/<year>/<season>/week_<week_number>.json")

    # Provide info about integrating with GitHub Pages
    print("\nFor GitHub Pages:")
    print("1. JSON files will be served statically from the docs/ directory")
    print(
        "2. These files will be automatically loaded when users select previous weeks"
    )
    print("3. Make sure to run this script before deploying to GitHub Pages")


if __name__ == "__main__":
    main()
