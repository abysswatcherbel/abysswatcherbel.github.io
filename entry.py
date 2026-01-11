import os
from datetime import datetime, timezone
from itertools import zip_longest
from dotenv import load_dotenv
from flask import Flask, abort, render_template, request, jsonify
from flask_frozen import Freezer
from pymongo import MongoClient
from src.rank_processing import (
    get_available_seasons,
    get_season_averages,
    get_weekly_change,
)
from src.post_processing import get_active_posts, main
from static.assets import back_symbol, new_entry, right_new_entry
from util.seasonal_schedule import SeasonScheduler
from util.logger_config import logger
import json

load_dotenv()

app = Flask(__name__)
app.config["FREEZER_RELATIVE_URLS"] = True  # For proper relative paths
app.config["FREEZER_DESTINATION"] = "docs"  # GitHub Pages default folder
app.config["DEBUG"] = True
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["FREEZER_RELATIVE_URLS_PRETTY"] = True  # For pretty URLs
app.config["FREEZER_DEFAULT_MIMETYPE"] = "text/html"
freezer = Freezer(app)

episode_schedule = SeasonScheduler()
post_schedule = SeasonScheduler(schedule_type="post")

if (
    post_schedule.year is None
    or post_schedule.season_number is None
    or post_schedule.week_id is None
):
    raise RuntimeError("Could not determine current post schedule details")

# The Airing Period for the rank
rank_schedule = episode_schedule.get_schedule_for_date(
    year=post_schedule.year,
    season=post_schedule.season_number,
    week_id=post_schedule.week_id,
)
if rank_schedule is None:
    raise RuntimeError("Could not determine current episode schedule details")

airing_period = episode_schedule.get_airing_period(
    schedule_details=rank_schedule
)
client = MongoClient(os.getenv("MONGO_URI"))
available_seasons = get_available_seasons()


def _season_to_number(season: str) -> int:
    season = season.lower()
    mapping = {"winter": 1, "spring": 2, "summer": 3, "fall": 4}
    if season not in mapping:
        abort(404)
    return mapping[season]


def _build_forced_post_schedule(
    year: int, season: str, week: int
) -> SeasonScheduler:
    season_number = _season_to_number(season)

    probe = SeasonScheduler(schedule_type="post")
    schedule_details = probe.get_schedule_for_date(
        year=year, season=season_number, week_id=week
    )
    if schedule_details is None or schedule_details.week_id is None:
        abort(404)

    # Use a timestamp inside the requested week that keeps `schedule.year == year`.
    # This matters for winter week 1 which can start in the previous calendar year.
    forced_time = (
        schedule_details.end_date
        if getattr(schedule_details.end_date, "year", None) == year
        else schedule_details.start_date
    )

    return SeasonScheduler(schedule_type="post", post_time=forced_time)


def _airing_details_for_week(year: int, season: str, week: int):
    season_number = _season_to_number(season)
    schedule_details = episode_schedule.get_schedule_for_date(
        year=year, season=season_number, week_id=week
    )
    if schedule_details is None or schedule_details.week_id is None:
        abort(404)

    converted_start_date = schedule_details.start_date.strftime("%B, %d")
    converted_end_date = schedule_details.end_date.strftime("%B, %d")

    return {
        "airing_period": f"Airing Period: {converted_start_date} - {converted_end_date}",
        "season": season.lower(),
        "week_id": week,
    }


@app.route("/current_chart/", endpoint="current_chart")
def karma_rank():
    """
    Render the current karma rankings chart.

    Shows the top 30 anime of the current week, split into two columns.
    Includes total karma calculation for top 15 shows.

    Returns:
        rendered template: The current_chart.html template with context containing:
            - complete_rankings: Paired rankings for left and right columns
            - airing_details: Current airing period information
            - sum_karma: Total karma for top 15 shows
            - Various symbols for UI elements
    """

    current_shows = get_weekly_change(schedule=post_schedule)
    total_karma = sum([show["karma"] for show in current_shows[:15]])
    total_karma = f"{total_karma:,}"

    # Get top 15 for the left side
    left_rankings = current_shows[:15]
    # Get the next 15 entries for the right side (if they exist)
    right_rankings = current_shows[15:30]

    # Pair the two lists; if the right list is shorter, fill with None
    complete_rankings = list(zip_longest(left_rankings, right_rankings))

    return render_template(
        "rank.html",
        complete_rankings=complete_rankings,
        airing_details=airing_period,
        sum_karma=total_karma,
        back_symbol=back_symbol,
        new_entry=new_entry,
        right_new_entry=right_new_entry,
    )


@app.route("/<int:year>/<season>/<int:week>", endpoint="rank_for_week")
@app.route("/<int:year>/<season>/<int:week>/", endpoint="rank_for_week_slash")
def karma_rank_for_week(year: int, season: str, week: int):
    """Render `rank.html.j2` for an arbitrary (year, season, week).

    Useful when the current chart has already advanced to the next week but you
    need to review or tweak the HTML for a previous week.
    """

    forced_schedule = _build_forced_post_schedule(
        year=year, season=season, week=week
    )
    current_shows = get_weekly_change(schedule=forced_schedule)
    total_karma = sum([show["karma"] for show in current_shows[:15]])
    total_karma = f"{total_karma:,}"

    left_rankings = current_shows[:15]
    right_rankings = current_shows[15:30]
    complete_rankings = list(zip_longest(left_rankings, right_rankings))

    airing_details = _airing_details_for_week(
        year=year, season=season, week=week
    )

    return render_template(
        "rank.html.j2",
        complete_rankings=complete_rankings,
        airing_details=airing_details,
        sum_karma=total_karma,
        back_symbol=back_symbol,
        new_entry=new_entry,
        right_new_entry=right_new_entry,
    )


@app.route("/<int:year>/<season>/week_<int:week>.html", endpoint="show_week")
def show_week(year: int, season: str, week: int) -> str:
    """
    Dynamically render a specific week's chart.

    Args:
        year (int): The year of the chart
        season (str): The season (winter, spring, summer, fall)
        week (int): The week number

    Returns:
        rendered template: The specific week's chart template
    """
    # Validate season
    if season.lower() not in ["winter", "spring", "summer", "fall"]:
        abort(404)
    template_path = f"{year}/{season}/week_{week}.html"

    return render_template(template_path)


@app.route("/", endpoint="new_home")
def current_week():
    """
    Render the current week's anime karma rankings.

    Retrieves and processes the current week's anime discussion posts and their karma scores.
    Includes weekly changes, airing details, and season averages.

    Returns:
        rendered template: The current_week.html template with context containing:
            - current_shows: List of shows with their karma data
            - current_week_id: Identifier for the current week
            - airing_details: Information about the current airing period
            - average_shows: Season-wide averages for shows
            - active_discussions: Currently active discussion posts on r/anime (under the 48 hours rule)
    """

    current_shows = get_weekly_change(schedule=post_schedule)
    season_averages = get_season_averages(
        schedule=post_schedule,
    )

    active_discussions = get_active_posts()

    return render_template(
        "new_home.html",
        current_shows=current_shows,
        current_week_id=post_schedule.week_id,
        airing_details=airing_period,
        average_shows=season_averages,
        active_discussions=active_discussions,
        available_seasons=available_seasons,
        current_time=post_schedule.post_time,
    )


@app.route("/karma_watch.html", endpoint="karma_watch")
def karma_watch():
    """
    Render the Karma Watch page for comparing show karma progression.

    Allows users to select and compare different shows to visualize how
    their karma grew over time after episode discussions were posted.

    Returns:
        rendered template: The karma_watch.html template
    """
    # Get all available shows with karma progression data
    collection = client.anime.karma_watch

    # Get karma progression data for all tracked shows
    karma_data = list(
        collection.aggregate(
            [
                {
                    "$lookup": {
                        "from": "seasonals",
                        "localField": "mal_id",
                        "foreignField": "id",
                        "as": "seasonal_data",
                    }
                },
                {
                    "$set": {
                        "title": {
                            "$ifNull": [
                                {
                                    "$arrayElemAt": [
                                        "$seasonal_data.title_english",
                                        0,
                                    ]
                                },
                                {"$arrayElemAt": ["$seasonal_data.title", 0]},
                            ]
                        },
                        "images": {
                            "$arrayElemAt": ["$seasonal_data.images", 0]
                        },
                    }
                },
                {"$unset": "seasonal_data"},
                {
                    "$match": {
                        "mal_id": {"$ne": None},
                        "hourly_karma": {
                            "$not": {
                                "$elemMatch": {
                                    "karma": {
                                        "$type": "double",
                                        "$eq": float("nan"),
                                    }
                                }
                            }
                        },
                    }
                },
                {
                    "$project": {
                        "_id": 0,
                    }
                },
            ]
        )
    )

    # Save the data to a JSON file for the frontend to use
    karma_watch_path = os.path.join("static", "data", "karma_watch.json")
    os.makedirs(os.path.dirname(karma_watch_path), exist_ok=True)

    with open(karma_watch_path, "w") as f:
        json.dump(karma_data, f, indent=4)

    client.close()

    return render_template(
        "karma_watch.html",
        available_seasons=available_seasons,
        current_time=datetime.now(timezone.utc),
    )


@app.route("/committees.html", endpoint="committees")
def production_committees():
    """
    Render the Production Committees page.

    This page displays anime shows and their production committees,
    with simplified data focusing on the anime and its committee members.

    Returns:
        rendered template: The production_committees.html template with context
    """
    # Get filter parameters from request
    season = post_schedule.season_name
    year = post_schedule.year

    client = MongoClient(os.getenv("MONGO_URI"))
    db = client.anime

    # Get committee data, which saves a json to /static/data/committees.json
    committee_data = list(db.committees.find({}, {"_id": 0}))

    with open(os.path.join("static", "data", "committees.json"), "w") as f:
        json.dump(committee_data, f, indent=4)

    # Filters
    filter_seasons = ["winter", "spring", "summer", "fall"]
    filter_years = sorted(db.committees.distinct("year"), reverse=True)
    client.close()

    return render_template(
        "committees.html",
        available_seasons=available_seasons,
        filter_seasons=filter_seasons,
        filter_years=filter_years,
        current_season=season,
        current_year=year,
        current_time=datetime.now(timezone.utc),
    )


@app.route("/previous-weeks.html")
def previous_weeks():

    return render_template(
        "previous_weeks.html", available_seasons=available_seasons
    )


if __name__ == "__main__":
    import sys

    if "freeze" in sys.argv:

        @freezer.register_generator
        def current_chart():
            yield {}

        @freezer.register_generator
        def new_home():
            yield {}

        # Generator for karma_watch (no parameters)
        @freezer.register_generator
        def karma_watch():
            yield {}

        @freezer.register_generator
        def committees():
            # Yield for the main page
            yield {}

        freezer.freeze()
    elif "run" in sys.argv:
        main()
    else:
        app.run(host="0.0.0.0")
