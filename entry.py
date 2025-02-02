from flask import Flask, render_template, request
from pymongo import MongoClient
from datetime import datetime, timezone
import os
from src.reddit_api import get_week_id, get_season, main  # Import necessary functions
from src.rank_processing import get_weekly_change, get_airing_period
from static.assets import back_symbol, new_entry, right_new_entry
from itertools import zip_longest
from flask_frozen import Freezer

app = Flask(__name__)
app.config['FREEZER_RELATIVE_URLS'] = True  # For proper relative paths
app.config['FREEZER_DESTINATION'] = 'docs'  # GitHub Pages default folder
freezer = Freezer(app)


@app.route('/')
def current_week():
    # Calculate current week_id
    current_time = datetime.now(timezone.utc)
    current_week_id = get_week_id('post',current_time)
    
    # Connect to MongoDB
    client = MongoClient(os.getenv('MONGO_URI'))
    


    current_shows = get_weekly_change()
    airing_details = get_airing_period()
    total_karma = sum([show['karma'] for show in current_shows[:15]])

    
    # # Fetch queued shows from scheduler jobs
    # scheduler_db = client.scheduler
    # apscheduler_jobs = scheduler_db.jobs
    # queued_jobs = list(apscheduler_jobs.find(
    #     {'next_run_time': {'$ne': None}},
    #     {'name': 1, 'next_run_time': 1}
    # ))
    
    # # Convert next_run_time to datetime
    # for job in queued_jobs:
    #     if 'next_run_time' in job:
    #         job['scheduled_time'] = datetime.fromtimestamp(job['next_run_time'], tz=timezone.utc)
    #         job['_id'] = job['_id'].split('_')[-1]
       
    
    client.close()
    return render_template(
        'current_week.html',
        current_shows=current_shows,
        current_week_id=current_week_id,
        airing_details=airing_details
    )

@app.route('/previous_weeks.html' ,endpoint='previous_weeks')
def previous_weeks():
    client = MongoClient(os.getenv('MONGO_URI'))
    db = client.anime
    seasonal_entries = db.seasonal_entries
    
    # Get all distinct week_ids
    pipeline = [
        {'$unwind': '$reddit_karma'},
        {'$group': {'_id': '$reddit_karma.week_id'}},
        {'$sort': {'_id': -1}}
    ]
    week_ids = [week['_id'] for week in seasonal_entries.aggregate(pipeline)]
    
    selected_week = request.args.get('week')
    selected_data = []
    if selected_week:
        selected_week = int(selected_week)
        pipeline = [
            {'$unwind': '$reddit_karma'},
            {'$match': {'reddit_karma.week_id': selected_week}},
            {'$project': {
                'title': 1,
                'episode': '$reddit_karma.episode',
                'karma': '$reddit_karma.karma',
                'comments': '$reddit_karma.comments',
                'url': '$reddit_karma.url'
            }}
        ]
        selected_data = list(seasonal_entries.aggregate(pipeline))
    
    client.close()
    return render_template(
        'previous_weeks.html',
        week_ids=week_ids,
        selected_week=selected_week,
        selected_data=selected_data
    )

@app.route('/current_chart.html', endpoint='current_chart')
def karma_rank():

    current_shows = get_weekly_change()
    airing_details = get_airing_period()
    total_karma = sum([show['karma'] for show in current_shows[:15]])
    total_karma = f'{total_karma:,}'

    # Get top 15 for the left side
    left_rankings = current_shows[:15]
    # Get the next 15 entries for the right side (if they exist)
    right_rankings = current_shows[15:30]

    # Pair the two lists; if the right list is shorter, fill with None
    complete_rankings = list(zip_longest(left_rankings, right_rankings))

    return render_template(
        'current_chart.html',
        complete_rankings=complete_rankings,
        airing_details=airing_details,
        sum_karma=total_karma,
        back_symbol=back_symbol,
        new_entry=new_entry,
        right_new_entry=right_new_entry,
    )


if __name__ == "__main__":
    import sys

    if "freeze" in sys.argv:
        # Generate static files
        freezer.freeze()
    else:
        # Run Flask app for local debugging
        app.run(debug=True)
