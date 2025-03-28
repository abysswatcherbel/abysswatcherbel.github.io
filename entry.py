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
    update_mal_numbers,
)
from src.post_processing import get_active_posts, main
from static.assets import back_symbol, new_entry, right_new_entry
from util.logger_config import logger
from util.seasonal_schedule import SeasonScheduler

load_dotenv()

app = Flask(__name__)
app.config["FREEZER_RELATIVE_URLS"] = True  # For proper relative paths
app.config["FREEZER_DESTINATION"] = "docs"  # GitHub Pages default folder
freezer = Freezer(app)

episode_schedule = SeasonScheduler()
post_schedule = SeasonScheduler(schedule_type="post")

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

    current_shows = get_weekly_change(current_time=episode_schedule.post_time, current_week=episode_schedule.get_week_id())
    airing_details = episode_schedule.get_airing_period()
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
def show_week(year: int, season: str, week: int)-> str:
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
    # Calculate current week_id
    current_time = post_schedule.post_time
    current_week_id = post_schedule.get_week_id()

    current_shows = get_weekly_change(current_time=current_time, current_week=current_week_id)
    airing_details = episode_schedule.get_airing_period()

    logger.debug(f"Airing details {airing_details} for the Current week: {current_week_id}")  

    season_averages = get_season_averages(
        season=airing_details["season"], year=current_time.year
    )
    available_seasons = get_available_seasons()
    active_discussions = get_active_posts()
    
    logger.debug(f"Available seasons: {available_seasons}")  

    return render_template(
        "new_home.html",
        current_shows=current_shows,
        current_week_id=current_week_id,
        airing_details=airing_details,
        average_shows=season_averages,
        active_discussions=active_discussions,
        available_seasons=available_seasons,
        current_time=current_time,
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
    client = MongoClient(os.getenv("MONGO_URI"))
    collection = client.anime.karma_watch
    
    # Get karma progression data for all tracked shows
    karma_data = list(collection.find(
    {
        "mal_id": {"$ne": None},
        "hourly_karma": {
            "$not": {
                "$elemMatch": {"karma": {"$type": "double", "$eq": float('nan')}}
            }
        }
    },
    {"_id": 0}
))

    
    # Save the data to a JSON file for the frontend to use
    karma_watch_path = os.path.join('static', 'data', 'karma_watch.json')
    os.makedirs(os.path.dirname(karma_watch_path), exist_ok=True)
    
    with open(karma_watch_path, 'w') as f:
        json.dump(karma_data, f)
    
    client.close()
    
    # Get available seasons for the navigation dropdown
    available_seasons = get_available_seasons()
    
    return render_template(
        "karma_watch.html",
        available_seasons=available_seasons,
        current_time=datetime.now(timezone.utc),
    )


if __name__ == "__main__":
    import sys

    if "freeze" in sys.argv:
        # Generate static files
        freezer.freeze()
    elif "update_mal" in sys.argv:
        # Update MAL Scores
        week_id = get_week_id("post")
        update_mal_numbers(week_id)
    elif "run" in sys.argv:
        main()
    else:
        app.run(debug=True, use_reloader=False)
