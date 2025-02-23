from pymongo import MongoClient
from pymongo.errors import OperationFailure
from datetime import datetime, timezone
import os
import requests
import time
import pandas as pd
from datetime import datetime, timezone
import os
import pandas as pd


def get_week_id(schedule_type: str = "episodes", post_time: datetime = None):
    if post_time is None:
        post_time = datetime.now(timezone.utc)

    if schedule_type not in ("post", "episodes"):
        raise ValueError("Invalid schedule_type. Must be either 'post' or 'episodes'.")

    year = post_time.year
    month = post_time.month
    season = get_season_name(month)

    if schedule_type == "episodes":
        schedule_path = os.path.join(
            "src/season_references", str(year), season, "episodes.csv"
        )
    else:
        schedule_path = os.path.join(
            "src/season_references", str(year), season, "post.csv"
        )

    schedule_df = pd.read_csv(schedule_path)

    # Convert start_date and end_date to timezone-aware datetimes (UTC)
    schedule_df["start_date"] = pd.to_datetime(schedule_df["start_date"], utc=True)
    schedule_df["end_date"] = pd.to_datetime(schedule_df["end_date"], utc=True)
    # Adjust end_date to cover the entire day by setting it to 23:59:59.999999
    schedule_df["end_date"] = (
        schedule_df["end_date"] + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
    )

    # Ensure post_time is timezone-aware (convert if needed)
    if post_time.tzinfo is None:
        post_time = post_time.replace(tzinfo=timezone.utc)

    for _, row in schedule_df.iterrows():
        if row["start_date"] <= post_time <= row["end_date"]:
            return row["week_id"]
    return None


def get_season_name(month_int):
    if month_int in range(1, 4):
        return "winter"
    elif month_int in range(4, 7):
        return "spring"
    elif month_int in range(7, 10):
        return "summer"
    elif month_int in range(10, 13):
        return "fall"
    else:
        raise ValueError(
            "Invalid month integer. Please provide a value between 1 and 12."
        )


def get_season(month_int):
    if month_int in range(1, 4):
        return 1
    elif month_int in range(4, 7):
        return 2
    elif month_int in range(7, 10):
        return 3
    elif month_int in range(10, 13):
        return 4
    else:
        raise ValueError(
            "Invalid month integer. Please provide a value between 1 and 12."
        )


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


def get_ids_current_week():
    """Fetch MAL IDs of all shows airing in the current week."""
    client = MongoClient(os.getenv("MONGO_URI"))
    db = client.anime
    seasonal_entries = db.winter_2025

    # Determine current week
    current_time = datetime.now(timezone.utc)
    current_week = get_week_id(schedule_type="post", post_time=current_time)

    # Fetch MAL IDs of shows airing in the current week
    mal_ids = list(
        seasonal_entries.distinct("mal_id", {"reddit_karma.week_id": current_week})
    )
    client.close()
    return mal_ids


def get_weekly_change():
    """Calculate weekly rank and karma changes using MongoDB data."""
    client = MongoClient(os.getenv("MONGO_URI"))
    db = client.anime
    seasonal_entries = db.winter_2025

    # Determine current week and season
    current_time = datetime.now(timezone.utc)
    current_week = get_week_id(schedule_type="post", post_time=current_time)
    current_month = current_time.month
    season = get_season(current_month)

    # Calculate last week ID
    last_week = 13 if current_week == 1 else current_week - 1

    # Fetch current week's data
    current_data = list(
        seasonal_entries.aggregate(
            [
                {"$unwind": "$reddit_karma"},
                {"$match": {"reddit_karma.week_id": current_week}},
                {
                    "$project": {
                        "_id": 0,
                        "title": 1,
                        "title_english": 1,
                        "episode": "$reddit_karma.episode",
                        "karma": "$reddit_karma.karma",
                        "comments": "$reddit_karma.comments",
                        "week_id": "$reddit_karma.week_id",
                        "images": 1,
                        "studio": "$studios.name",
                        "score": "$reddit_karma.mal_stats.score",
                        "streaming_on": 1,
                        "url": "$reddit_karma.url",
                        "mal_id": 1,
                        "mal_url": "$external_links.mal",
                        "synopsis": 1,
                        "trailer": 1,
                        "streams": {
                            "$cond": {
                                "if": {
                                    "$and": [
                                        {"$ne": ["$streams", None]},
                                        {"$ne": ["$streaming_on", None]},
                                    ]
                                },
                                "then": {
                                    "$getField": {
                                        "field": "$streaming_on",
                                        "input": "$streams",
                                    }
                                },
                                "else": None,
                            }
                        },
                    }
                },
            ]
        )
    )

    # Fetch previous week's data
    previous_data = list(
        seasonal_entries.aggregate(
            [
                {"$unwind": "$reddit_karma"},
                {"$match": {"reddit_karma.week_id": last_week}},
                {
                    "$project": {
                        "_id": 0,
                        "title": 1,
                        "title_english": 1,
                        "episode": "$reddit_karma.episode",
                        "karma": "$reddit_karma.karma",
                        "comments": "$reddit_karma.comments",
                        "week_id": "$reddit_karma.week_id",
                        "mal_id": 1,
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
        romaji = current_entry["title"]
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
    return merged_data


def fetch_mal_score(
    mal_ids: list[int],
    headers: dict = {"X-MAL-CLIENT-ID": os.getenv("MAL_SECRET")},
    current_week=get_week_id(schedule_type="post"),
):

    if not isinstance(mal_ids, list):
        mal_ids = [mal_ids]
    for mal_id in mal_ids:
        try:
            endpoint = f"https://api.myanimelist.net/v2/anime/{mal_id}?fields=id,mean,rank,popularity,num_list_users,num_scoring_users,statistics"

            response = requests.get(url=endpoint, headers=headers)
            if response.status_code == 200:
                data = response.json()
                process_stats(data, current_week)

            else:
                print(f"Error with ID {mal_id}: {response.status_code}")
        except Exception as e:
            print(f"Error with ID {mal_id}: {e}")


def process_stats(data: dict, current_week):

    mal_id = data.get("id")
    # Transform API response into the correct statistics format

    client = MongoClient(os.getenv("MONGO_URI"))
    db = client.anime
    col = db.winter_2025

    mal_score = data.get("mean")
    mal_members = data.get("num_list_users")
    mal_scoring_members = data.get("num_scoring_users")

    col.update_one(
        {"mal_id": mal_id},
        {
            "$set": {
                "score": mal_score,
                "members": mal_members,
                "scored_by": mal_scoring_members,
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
        "mal_id": mal_id,
        "reddit_karma.week_id": current_week,
        "mal_stats": new_statistic,
    }

    col.update_one(
        {"mal_id": mal_id, "reddit_karma.week_id": current_week},
        {"$set": {"reddit_karma.$.mal_stats": new_statistic}},
    )
    client.close()

    return pipeline


def get_airing_period(
    current_time=datetime.now(timezone.utc), schedule_type: str = "episodes"
):
    """Get the airing period for the current week."""
    current_year = current_time.year
    week_id = get_week_id(schedule_type=schedule_type)
    current_month = current_time.month
    season_name = get_season_name(current_month)

    # Define the path to the episodes.csv file
    schedule_path = os.path.join(
        "src",
        "season_references",
        str(current_year),
        season_name,
        f"{schedule_type}.csv",
    )

    # Load the CSV file into a DataFrame
    try:
        schedule_df = pd.read_csv(schedule_path)
    except FileNotFoundError:
        return f"CSV file not found at {schedule_path}"

    # Convert 'start_date' and 'end_date' columns to datetime
    schedule_df["start_date"] = pd.to_datetime(schedule_df["start_date"])
    schedule_df["end_date"] = pd.to_datetime(schedule_df["end_date"])

    # Filter the DataFrame by week_id
    week_row = schedule_df[schedule_df["week_id"] == week_id]

    if week_row.empty:
        return f"No schedule found for week_id: {week_id}"

    # Get start_date and end_date from the filtered row
    start_date = week_row["start_date"].iloc[0]
    end_date = week_row["end_date"].iloc[0]

    # Convert the dates to the desired format, e.g., "September, 20"
    converted_start_date = start_date.strftime("%B, %d")
    converted_end_date = end_date.strftime("%B, %d")

    airing_period = f"Airing Period: {converted_start_date} - {converted_end_date}"

    airing_details = {
        "airing_period": airing_period,
        "season": season_name,
        "week_id": week_id,
    }

    # Return the formatted airing period
    return airing_details


def get_season_averages(season: str, year: int):
    # 1. Connect to your MongoDB
    client = MongoClient(os.getenv("MONGO_URI"))

    # 2. Get your specific database and collection
    db = client.anime
    collection = db[f"{season}_{year}"]
    try:
        db.validate_collection(collection)
    except OperationFailure:
        return

    pipeline = [
        {"$match": {"reddit_karma": {"$exists": True, "$type": "array"}}},
        {"$match": {"$expr": {"$gte": [{"$size": "$reddit_karma"}, 3]}}},
        {
            "$project": {
                "_id": 0,
                "mal_id": 1,
                "title": 1,
                "title_english": 1,
                "images": 1,
                "average_karma": {"$avg": "$reddit_karma.karma"},
                "average_comments": {"$avg": "$reddit_karma.comments"},
                "max_karma": {"$max": "$reddit_karma.karma"},
                "min_karma": {"$min": "$reddit_karma.karma"},
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


def update_mal_numbers(week_id: int):
    # 1. Connect to your MongoDB
    client = MongoClient(os.getenv("MONGO_URI"))

    # 2. Get your specific database and collection
    db = client.anime
    collection = db.winter_2025
    try:
        db.validate_collection(collection)
    except OperationFailure:
        return

    pipeline = [
        {"$match": {"reddit_karma": {"$elemMatch": {"week_id": week_id}}}},
        {"$project": {"_id": 0, "mal_id": 1}},
    ]

    mal_ids = list(collection.aggregate(pipeline))
    mal_ids = [entry["mal_id"] for entry in mal_ids]
    client.close()
    fetch_mal_score(mal_ids)


def get_available_seasons():
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
                        seasons_data[year][season] = sorted(weeks)

    return seasons_data
