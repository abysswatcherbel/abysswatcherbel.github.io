import json
import os
from datetime import datetime, timezone
from itertools import zip_longest

from dotenv import load_dotenv
from flask import Flask, abort, render_template, request
from flask_frozen import Freezer
from pymongo import MongoClient

from src.rank_processing import (
    get_airing_period,
    get_available_seasons,
    get_season_averages,
    get_week_id,
    get_weekly_change,
    update_mal_numbers
)
from src.post_processing import get_active_posts, main
from static.assets import back_symbol, new_entry, right_new_entry

load_dotenv()

app = Flask(__name__)
app.config["FREEZER_RELATIVE_URLS"] = True  # For proper relative paths
app.config["FREEZER_DESTINATION"] = "docs"  # GitHub Pages default folder
freezer = Freezer(app)


@app.route("/")
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
    # Calculate current week_id
    current_time = datetime.now(timezone.utc)
    current_week_id = get_week_id("post", current_time)

    # Connect to MongoDB
    client = MongoClient(os.getenv("MONGO_URI"))
    collection = client.anime.hourly_data

    current_shows = get_weekly_change()
    airing_details = get_airing_period()
    season_averages = get_season_averages(
        season=airing_details["season"], year=current_time.year
    )
    available_seasons = get_available_seasons()
    active_discussions = get_active_posts()
    progression_data = list(
        collection.find(
            {"week_id": airing_details["week_id"]},
            {"_id": 0, "mal_id": 1, "progression": 1},
        )
    )

    with open(os.getenv("JSON_PATH"), "w") as f:
        json.dump(progression_data, f)

    client.close()
    print(f"Available seasons: {available_seasons}")  # Debug print
    return render_template(
        "current_week.html",
        current_shows=current_shows,
        current_week_id=current_week_id,
        airing_details=airing_details,
        average_shows=season_averages,
        active_discussions=active_discussions,
        available_seasons=available_seasons,
    )


@app.route("/current_chart.html", endpoint="current_chart")
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

    current_shows = get_weekly_change()
    airing_details = get_airing_period(schedule_type="post")
    total_karma = sum([show["karma"] for show in current_shows[:15]])
    total_karma = f"{total_karma:,}"

    # Get top 15 for the left side
    left_rankings = current_shows[:15]
    # Get the next 15 entries for the right side (if they exist)
    right_rankings = current_shows[15:30]

    # Pair the two lists; if the right list is shorter, fill with None
    complete_rankings = list(zip_longest(left_rankings, right_rankings))

    return render_template(
        "current_chart.html",
        complete_rankings=complete_rankings,
        airing_details=airing_details,
        sum_karma=total_karma,
        back_symbol=back_symbol,
        new_entry=new_entry,
        right_new_entry=right_new_entry,
    )


@app.route("/<int:year>/<season>/week_<int:week>.html", endpoint="show_week")
def show_week(year, season, week):
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
    print(f"Looking for template at: {template_path}")  # Debug print
    return render_template(template_path)


if __name__ == "__main__":
    import sys

    if "freeze" in sys.argv:
        # Generate static files
        # week_id = get_week_id("post")
        # update_mal_numbers(week_id)
        freezer.freeze()
    elif "run" in sys.argv:
        # Run Flask app for local debugging
        main()
    else:
        app.run(debug=True, use_reloader=False)
