import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from pymongo import MongoClient
from util.logger_config import logger
from dotenv import load_dotenv
load_dotenv()


def save_weekly_ranking(data, year, season, week_id):
    """
    Save weekly ranking data to both JSON.

    Args:
        data (list): List of show data from get_weekly_change
        year (int): Year of the season
        season (str): Season name (winter, spring, summer, fall)
        week_id (int): Week number

    Returns:
        bool: Success status of the operation
    """
    try:
        # 1. Save to JSON file
        save_path = Path("static/data") / str(year) / season
        os.makedirs(save_path, exist_ok=True)

        json_path = save_path / f"week_{week_id}.json"
        with open(json_path, "w") as f:
            json.dump(data, f, indent=2)

        logger.info(f"Saved weekly ranking to JSON: {json_path}")

        return True

    except Exception as e:
        logger.error(f"Error saving weekly ranking data: {e}")
        return False


def load_weekly_ranking(year, season, week_id):
    """
    Load weekly ranking data, trying JSON first then falling back to SQLite if needed.

    Args:
        year (int): Year of the season
        season (str): Season name (winter, spring, summer, fall)
        week_id (int): Week number

    Returns:
        list: List of show data for the specified week
    """
    try:
        # Try to load from JSON first
        json_path = Path("static/data") / str(year) / season / f"week_{week_id}.json"
        if json_path.exists():
            with open(json_path, "r") as f:
                data = json.load(f)
                logger.info(f"Loaded weekly ranking from JSON: {json_path}")
                return data

        logger.warning(
            f"No weekly ranking data found for {year}/{season}/week_{week_id}"
        )
        return None

    except Exception as e:
        logger.error(f"Error loading weekly ranking data: {e}")
        return None


def get_available_seasons_from_db(mongo_uri=None):
    """
    Get all available years and seasons with weekly rankings from MongoDB.

    Args:
        mongo_uri (str, optional): MongoDB connection URI. Defaults to None (uses environment variable).

    Returns:
        dict: Dictionary with years and seasons available in the database
    """
    import os

    if mongo_uri is None:
        mongo_uri = os.getenv("MONGO_URI")

    try:
        client = MongoClient(mongo_uri)
        db = client.anime
        seasonals = db.seasonals

        # Find all documents with reddit_karma data
        pipeline = [
            {"$project": {"_id": 0, "reddit_karma": 1}},
            {"$match": {"reddit_karma": {"$exists": True}}},
        ]

        results = list(seasonals.aggregate(pipeline))
        logger.debug(f'Found {len(results)} documents with reddit_karma data, sample {results[0]}')

        # Process results to find unique years and seasons
        available_seasons = {}

        for doc in results:
            if doc.get("reddit_karma"):
                karma_data = doc.get("reddit_karma")
                for year, seasons in karma_data.items():
                    if year not in available_seasons:
                        available_seasons[year] = {}

                    for season, weeks_data in seasons.items():
                        if season not in available_seasons[year]:
                            available_seasons[year][season] = []

                        # Extract unique week IDs
                        week_ids = sorted(
                            list(set(entry.get("week_id") for entry in weeks_data))
                        )
                        available_seasons[year][season] = week_ids

        client.close()
        logger.info(
            f"Found {len(available_seasons)} years with seasonal data in the database"
        )
        return available_seasons

    except Exception as e:
        logger.error(f"Error getting available seasons from database: {e}")
        return {}


def backup_weekly_rankings(mongo_uri=None, specific_year=None, specific_season=None):
    """
    Generate JSON backups for weekly rankings from MongoDB data.

    This function fetches data from MongoDB and creates JSON files in the static/data directory
    for all available weeks of all seasons, or for a specific year/season if specified.

    Args:
        mongo_uri (str, optional): MongoDB connection URI. Defaults to None (uses environment variable).
        specific_year (str, optional): Specific year to backup. Defaults to None (all years).
        specific_season (str, optional): Specific season to backup. Defaults to None (all seasons).

    Returns:
        dict: Summary of the backup operation
    """
    import os
    from src.rank_processing import assign_rank

    if mongo_uri is None:
        mongo_uri = os.getenv("MONGO_URI")

    summary = {
        "success": False,
        "years_processed": 0,
        "seasons_processed": 0,
        "weeks_processed": 0,
        "errors": [],
    }

    try:
        client = MongoClient(mongo_uri)
        db = client.anime
        seasonals = db.seasonals

        # Get available seasons or filter by specific year/season
        available_seasons = get_available_seasons_from_db(mongo_uri)

        if specific_year:
            available_seasons = {
                k: v for k, v in available_seasons.items() if k == specific_year
            }

        if not available_seasons:
            logger.warning(f"No data found for year: {specific_year}")
            return summary

        # Process each year and season
        for year, seasons in available_seasons.items():
            if specific_season:
                seasons = {k: v for k, v in seasons.items() if k == specific_season}

            if not seasons:
                logger.warning(
                    f"No data found for year {year}, season: {specific_season}"
                )
                continue

            for season, weeks in seasons.items():
                for week_id in weeks:
                    try:
                        # Fetch data for this week
                        reddit_karma = f"reddit_karma.{year}.{season}"
                        current_data = list(
                            seasonals.aggregate(
                                [
                                    {"$unwind": f"${reddit_karma}"},
                                    {"$match": {f"{reddit_karma}.week_id": week_id}},
                                    {
                                        "$project": {
                                            "_id": 0,
                                            "title": 1,
                                            "title_english": 1,
                                            "episode": f"${reddit_karma}.episode",
                                            "karma": f"${reddit_karma}.karma",
                                            "comments": f"${reddit_karma}.comments",
                                            "week_id": f"${reddit_karma}.week_id",
                                            "images": 1,
                                            "banner": f"${reddit_karma}.banner",
                                            "studio": "$studios.name",
                                            "score": 1,
                                            "streams": 1,
                                            "url": f"${reddit_karma}.url",
                                            "mal_id": "$id",
                                            "num_episodes": 1,
                                        }
                                    },
                                ]
                            )
                        )

                        # Calculate rankings
                        if current_data:
                            current_sorted = sorted(
                                current_data,
                                key=lambda x: (-x["karma"], -x["comments"]),
                            )
                            current_sorted = assign_rank(current_sorted)

                            for entry in current_sorted:
                                entry["current_rank"] = entry.pop("rank", None)
                                # Add season info and placeholder for rank change
                                entry["season"] = season
                                entry["rank_change"] = 0  # Default value
                                entry["karma_change"] = 0  # Default value

                            # Save the data
                            success = save_weekly_ranking(
                                current_sorted, year, season, week_id
                            )

                            if success:
                                summary["weeks_processed"] += 1
                            else:
                                summary["errors"].append(
                                    f"Failed to save {year}/{season}/week_{week_id}"
                                )

                    except Exception as e:
                        error_msg = (
                            f"Error processing {year}/{season}/week_{week_id}: {str(e)}"
                        )
                        logger.error(error_msg)
                        summary["errors"].append(error_msg)

                summary["seasons_processed"] += 1

            summary["years_processed"] += 1

        client.close()

        summary["success"] = len(summary["errors"]) == 0
        logger.info(
            f"Backup completed: {summary['weeks_processed']} weeks from {summary['seasons_processed']} seasons processed"
        )

        return summary

    except Exception as e:
        logger.error(f"Error during backup operation: {e}")
        summary["errors"].append(str(e))
        return summary
