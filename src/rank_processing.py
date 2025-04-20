from pymongo import MongoClient
from pymongo.errors import OperationFailure
from datetime import datetime, timezone
import os
import requests
import time
import pandas as pd
from datetime import datetime, timezone
import os
from util.logger_config import logger
from util.mal import MalImages
from util.seasonal_schedule import SeasonScheduler
from util.data_backup import save_weekly_ranking
from pydantic import BaseModel
from typing import List, Optional


class KarmaRankEntry(BaseModel):
    rank: int
    title: str
    karma: int
    comments: int
    episode: str
    studio: str
    streaming_on: str
    url: str
    mal_id: int
    images: MalImages
    score: float


class KarmaRank(BaseModel):
    entries: List[KarmaRankEntry]


def assign_rank(sorted_entries):
    """Assign ranks to sorted entries, handling ties with 'min' method."""
    if not sorted_entries:
        return []
    current_rank = 1
    sorted_entries[0]["rank"] = current_rank
    previous_karma = sorted_entries[0]["karma"]
    previous_comments = sorted_entries[0]["comments"]

    for i in range(1, len(sorted_entries)):
        entry = sorted_entries[i]
        if entry["karma"] == previous_karma and entry["comments"] == previous_comments:
            entry["rank"] = current_rank
        else:
            current_rank = i + 1
            entry["rank"] = current_rank
            previous_karma = entry["karma"]
            previous_comments = entry["comments"]
    return sorted_entries


def get_weekly_change(schedule: SeasonScheduler):
    """Calculate weekly rank and karma changes using MongoDB data."""
    client = MongoClient(os.getenv("MONGO_URI"))
    db = client.anime
    seasonal_entries = db.seasonals

    # Determine current week and season
    current_week = schedule.week_id
    season = schedule.season_name
    year = schedule.year

    reddit_karma = f"reddit_karma.{year}.{season}"

    # Calculate last week ID
    last_week = 13 if current_week == 1 else current_week - 1

    # Fetch current week's data
    current_data = list(
        seasonal_entries.aggregate(
            [
                {"$unwind": f"${reddit_karma}"},
                {"$match": {f"{reddit_karma}.week_id": current_week}},
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
                        "banner": 1,
                    }
                },
            ]
        )
    )

    # Fetch previous week's data
    reddit_karma = (
        f"reddit_karma.{year}.{season}"
        if last_week != 13
        else f"reddit_karma.{year}.{schedule._get_season_name(schedule.season_number - 1)}"
    )
    previous_data = list(
        seasonal_entries.aggregate(
            [
                {"$unwind": f"${reddit_karma}"},
                {"$match": {f"{reddit_karma}.week_id": last_week}},
                {
                    "$project": {
                        "_id": 0,
                        "title": 1,
                        "title_english": 1,
                        "episode": f"${reddit_karma}.episode",
                        "karma": f"${reddit_karma}.karma",
                        "comments": f"${reddit_karma}.comments",
                        "week_id": f"${reddit_karma}.week_id",
                        "mal_id": "$id",
                    }
                },
            ]
        )
    )

    # Sort and rank current and previous data
    current_sorted = sorted(current_data, key=lambda x: (-x["karma"], -x["comments"]))
    current_sorted = assign_rank(current_sorted)
    for entry in current_sorted:
        entry["current_rank"] = entry.pop("rank", None)

    previous_sorted = sorted(previous_data, key=lambda x: (-x["karma"], -x["comments"]))
    previous_sorted = assign_rank(previous_sorted)
    for entry in previous_sorted:
        entry["previous_rank"] = entry.pop("rank", None)

    # Build previous week lookup
    previous_dict = {entry["mal_id"]: entry for entry in previous_sorted}

    # Merge data and compute changes
    merged_data = []
    for current_entry in current_sorted:

        mal_id = current_entry["mal_id"]
        previous_entry = previous_dict.get(mal_id, {})

        # Calculate karma change
        karma_change = (
            current_entry["karma"] - previous_entry.get("karma", 0)
            if mal_id in previous_dict
            else 0
        )

        # Determine rank change
        if mal_id in previous_dict:
            rank_change = (
                previous_entry["previous_rank"] - current_entry["current_rank"]
            )
        else:
            rank_change = "new" if current_entry["episode"] == "1" else "returning"

        merged_entry = {
            **current_entry,
            "karma_change": karma_change,
            "rank_change": rank_change,
            "season": season,
        }
        merged_data.append(merged_entry)

    client.close()

    # Save the weekly ranking data to JSON
    try:
        save_weekly_ranking(merged_data, year, season, current_week)
        logger.info(
            f"Saved weekly ranking data for {year} {season} week {current_week}"
        )
    except Exception as e:
        logger.error(f"Failed to save weekly ranking data: {e}")

    return merged_data


def process_stats(data: dict, current_week):

    mal_id = data.get("id")
    # Transform API response into the correct statistics format

    client = MongoClient(os.getenv("MONGO_URI"))
    db = client.anime
    col = db.seasonals

    mal_score = data.get("mean")
    mal_members = data.get("num_list_users")
    mal_scoring_members = data.get("num_scoring_users")

    col.update_one(
        {"id": mal_id},
        {
            "$set": {
                "score": mal_score,
                "members": mal_members,
            }
        },
    )

    new_statistic = {
        "score": mal_score,
        "members": mal_members,
        "scoring_members": mal_scoring_members,
        "extra_stats": data["statistics"]["status"],
    }

    pipeline = {
        "id": mal_id,
        "reddit_karma.week_id": current_week,
        "mal_stats": new_statistic,
    }

    col.update_one(
        {"id": mal_id, "reddit_karma.2025.winter.week_id": current_week},
        {"$set": {"reddit_karma.$.mal_stats": new_statistic}},
    )
    client.close()

    return pipeline


def get_season_averages(schedule: SeasonScheduler):
    # 1. Connect to your MongoDB
    client = MongoClient(os.getenv("MONGO_URI"))
    season = schedule.season_name
    year = schedule.year

    logger.debug(f"Getting season averages for {season} {year}")

    # 2. Get your specific database and collection
    db = client.anime
    collection = db.seasonals
    try:
        db.validate_collection(collection)
    except OperationFailure:
        return

    pipeline = [
        {
            "$match": {
                f"reddit_karma.{year}.{season}": {"$exists": True, "$type": "array"}
            }
        },
        {
            "$match": {
                "$expr": {"$gte": [{"$size": f"$reddit_karma.{year}.{season}"}, 2]}
            }
        },
        {
            "$project": {
                "_id": 0,
                "mal_id": "$id",
                "title": 1,
                "title_english": 1,
                "images": 1,
                "streams": 1,
                "average_karma": {"$avg": f"$reddit_karma.{year}.{season}.karma"},
                "average_comments": {"$avg": f"$reddit_karma.{year}.{season}.comments"},
                "max_karma": {"$max": f"$reddit_karma.{year}.{season}.karma"},
                "min_karma": {"$min": f"$reddit_karma.{year}.{season}.karma"},
                "total_episodes": {"$size": f"$reddit_karma.{year}.{season}"},
            }
        },
    ]

    try:
        season_averages = list(collection.aggregate(pipeline))
        client.close()
        season_averages = sorted(
            season_averages, key=lambda x: x["average_karma"], reverse=True
        )
        return season_averages
    except Exception as e:
        print(e)
        client.close()
        return


def update_mal_numbers(
    schedule: SeasonScheduler = SeasonScheduler(schedule_type="post"),
):
    # 1. Connect to your MongoDB
    client = MongoClient(os.getenv("MONGO_URI"))

    # 2. Get your specific database and collection
    db = client.anime
    collection = db.seasonals
    try:
        db.validate_collection(collection)
    except OperationFailure:
        return

    # Set the schedule related variables
    week_id = schedule.week_id
    year = schedule.year
    season = schedule.season_name
    reddit_karma = f"reddit_karma.{year}.{season}"

    pipeline = [
        {"$match": {reddit_karma: {"$elemMatch": {"week_id": week_id}}}},
        {"$project": {"_id": 0, "id": 1}},
    ]

    mal_ids = list(collection.aggregate(pipeline))
    mal_ids = [entry["id"] for entry in mal_ids]

    if mal_ids:

        for mal_id in mal_ids:
            try:
                logger.info(f"Getting mal_details for id: {mal_id}")
                endpoint = f"https://api.myanimelist.net/v2/anime/{mal_id}?fields=id,mean,rank,popularity,num_list_users,num_scoring_users,statistics"
                headers = {
                    "X-MAL-CLIENT-ID": os.getenv("MAL_SECRET"),
                }

                response = requests.get(url=endpoint, headers=headers, timeout=90)
                if response.status_code == 200:
                    data = response.json()
                    logger.success(f"Got MAL data for {mal_id}")
                    new_statistic = {
                        "score": data.get("mean"),
                        "members": data.get("num_list_users"),
                        "scoring_members": data.get("num_scoring_users"),
                        "extra_stats": data.get("statistics", {}).get("status"),
                    }

                    collection.update_one(
                        {"id": mal_id, f"{reddit_karma}.week_id": week_id},
                        {"$set": {f"{reddit_karma}.$.mal_stats": new_statistic}},
                    )

                    collection.update_one(
                        {"id": mal_id},
                        {
                            "$set": {
                                "score": data.get("mean"),
                                "members": data.get("num_list_users"),
                            }
                        },
                    )

                else:
                    logger.error(f"Error with ID {mal_id}: {response.status_code}")
            except Exception as e:
                logger.error(f"Error with ID {mal_id}: {e}")
    client.close()


def get_available_seasons() -> dict:
    """
    Get all available seasons and their weeks from the docs directory.

    Returns:
        dict: Nested dictionary of years, seasons, and their available weeks
        Example: {
            '2025': {
                'winter': ['week_5', 'week_6'],
                'spring': ['week_1', 'week_2']
            }
        }
    """
    seasons_data = {}
    docs_path = "templates"  # or your static files directory

    for year in os.listdir(docs_path):
        if year.isdigit():
            seasons_data[year] = {}
            year_path = os.path.join(docs_path, year)

            for season in os.listdir(year_path):
                if season in ["winter", "spring", "summer", "fall"]:
                    weeks = []
                    season_path = os.path.join(year_path, season)
                    for file in os.listdir(season_path):
                        if file.startswith("week_") and file.endswith(".html"):
                            weeks.append(file.replace(".html", ""))
                    if weeks:
                        # Sort the weeks numerically based on the week number
                        seasons_data[year][season] = sorted(
                            weeks, key=lambda x: int(x.replace("week_", ""))
                        )

    return seasons_data
