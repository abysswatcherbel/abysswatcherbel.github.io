from pymongo import MongoClient
from datetime import datetime, timezone
import os
from src.reddit_api import *
import requests
import time

def assign_rank(sorted_entries):
    """Assign ranks to sorted entries, handling ties with 'min' method."""
    if not sorted_entries:
        return []
    current_rank = 1
    sorted_entries[0]['rank'] = current_rank
    previous_karma = sorted_entries[0]['karma']
    previous_comments = sorted_entries[0]['comments']
    
    for i in range(1, len(sorted_entries)):
        entry = sorted_entries[i]
        if entry['karma'] == previous_karma and entry['comments'] == previous_comments:
            entry['rank'] = current_rank
        else:
            current_rank = i + 1
            entry['rank'] = current_rank
            previous_karma = entry['karma']
            previous_comments = entry['comments']
    return sorted_entries



def get_ids_current_week():
    """Fetch MAL IDs of all shows airing in the current week."""
    client = MongoClient(os.getenv('MONGO_URI'))
    db = client.anime
    seasonal_entries = db.winter_2025

    # Determine current week
    current_time = datetime.now(timezone.utc)
    current_week = get_week_id(schedule_type='post',post_time=current_time)

    # Fetch MAL IDs of shows airing in the current week
    mal_ids = list(seasonal_entries.distinct("mal_id", {"reddit_karma.week_id": current_week}))
    client.close()
    return mal_ids
def get_weekly_change():

    """Calculate weekly rank and karma changes using MongoDB data."""
    client = MongoClient(os.getenv('MONGO_URI'))
    db = client.anime
    seasonal_entries = db.winter_2025

    # Determine current week and season
    current_time = datetime.now(timezone.utc)
    current_week = get_week_id(schedule_type='post',post_time=current_time)
    current_month = current_time.month
    season = get_season(current_month)

    # Calculate last week ID
    last_week = 13 if current_week == 1 else current_week - 1

    # Fetch current week's data
    current_data = list(seasonal_entries.aggregate([
        {"$unwind": "$reddit_karma"},
        {"$match": {"reddit_karma.week_id": current_week}},
        {"$project": {
            "_id": 0,
            "title": 1,
            "title_english": 1,
            "episode": "$reddit_karma.episode",
            "karma": "$reddit_karma.karma",
            "comments": "$reddit_karma.comments",
            "week_id": "$reddit_karma.week_id",
            "default_banner": "$images.jpg.large_image_url",
            "studio": "$studios.name",
            "score": "$reddit_karma.mal_stats.score",
            "streaming_on": 1,
            "mal_id": 1
            
        }}
    ]))

    # Fetch previous week's data
    previous_data = list(seasonal_entries.aggregate([
        {"$unwind": "$reddit_karma"},
        {"$match": {"reddit_karma.week_id": last_week}},
        {"$project": {
            "_id": 0,
            "title": 1,
            "title_english": 1,
            "episode": "$reddit_karma.episode",
            "karma": "$reddit_karma.karma",
            "comments": "$reddit_karma.comments",
            "week_id": "$reddit_karma.week_id",
            "mal_id": 1
        }}
    ]))

    # Sort and rank current and previous data
    current_sorted = sorted(current_data, key=lambda x: (-x['karma'], -x['comments']))
    current_sorted = assign_rank(current_sorted)
    for entry in current_sorted:
        entry['current_rank'] = entry.pop('rank', None)

    previous_sorted = sorted(previous_data, key=lambda x: (-x['karma'], -x['comments']))
    previous_sorted = assign_rank(previous_sorted)
    for entry in previous_sorted:
        entry['previous_rank'] = entry.pop('rank', None)

    # Build previous week lookup
    previous_dict = {entry['mal_id']: entry for entry in previous_sorted}

    # Merge data and compute changes
    merged_data = []
    for current_entry in current_sorted:
        romaji = current_entry['title']
        mal_id = current_entry['mal_id']
        previous_entry = previous_dict.get(mal_id, {})

        # Calculate karma change
        karma_change = current_entry['karma'] - previous_entry.get('karma', 0) if mal_id in previous_dict else 0

        # Determine rank change
        if mal_id in previous_dict:
            rank_change = previous_entry['previous_rank'] - current_entry['current_rank'] 
        else:
            rank_change = 'new' if current_entry['episode'] == '1' else 'returning'

        merged_entry = {
            **current_entry,
            "karma_change": karma_change,
            "rank_change": rank_change,
            "season": season
        }
        merged_data.append(merged_entry)

    client.close()
    return merged_data

def fetch_mal_score(mal_ids: list[int], headers: dict = {"X-MAL-CLIENT-ID": os.getenv('MAL_SECRET') }, current_week = get_week_id(schedule_type='post')):
   
    if not isinstance(mal_ids, list):
        mal_ids = [mal_ids]
    for mal_id in mal_ids:
        try:
            endpoint = f'https://api.myanimelist.net/v2/anime/{mal_id}?fields=id,mean,rank,popularity,num_list_users,num_scoring_users,statistics'
            
            response = requests.get(url = endpoint, headers=headers)
            if response.status_code == 200:
                data = response.json()
                process_stats(data, current_week)
                time.sleep(1)
                
            else:
                print(f"Error with ID {mal_id}: {response.status_code}")
        except Exception as e:
            print(f"Error with ID {mal_id}: {e}")
  


def process_stats(data: dict, current_week):

    mal_id = data.get('id')
    # Transform API response into the correct statistics format
    new_statistic = {
        
        'score': data.get('mean'),
        'members' : data.get('num_list_users'),
        'scoring_members': data.get('num_scoring_users'),
        'extra_stats': data['statistics']['status']
        
    }

    pipeline = {"mal_id": mal_id, "reddit_karma.week_id": current_week, "mal_stats": new_statistic}

    client = MongoClient(os.getenv('MONGO_URI'))
    db = client.anime
    col = db.winter_2025
    result = col.update_one({"mal_id": mal_id, "reddit_karma.week_id": current_week},{"$set": {"reddit_karma.$.mal_stats": new_statistic}})
    print(f"Updated {result.modified_count} entries")
    client.close()
    

    return pipeline



def get_airing_period():

    current_time = datetime.now(timezone.utc)
    current_year = current_time.year
    week_id = get_week_id(schedule_type='post')
    current_month = current_time.month
    season_name = get_season_name(current_month)
    
    # Define the path to the episodes.csv file
    schedule_path = os.path.join('src', 'season_references', str(current_year), season_name, 'episodes.csv')
    
    # Load the CSV file into a DataFrame
    try:
        schedule_df = pd.read_csv(schedule_path)
    except FileNotFoundError:
        return f"CSV file not found at {schedule_path}"

    # Convert 'start_date' and 'end_date' columns to datetime
    schedule_df['start_date'] = pd.to_datetime(schedule_df['start_date'])
    schedule_df['end_date'] = pd.to_datetime(schedule_df['end_date'])

    # Filter the DataFrame by week_id
    week_row = schedule_df[schedule_df['week_id'] == week_id]

    if week_row.empty:
        return f"No schedule found for week_id: {week_id}"

    # Get start_date and end_date from the filtered row
    start_date = week_row['start_date'].iloc[0]
    end_date = week_row['end_date'].iloc[0]

    # Convert the dates to the desired format, e.g., "September, 20"
    converted_start_date = start_date.strftime("%B, %d")
    converted_end_date = end_date.strftime("%B, %d")

    airing_period = f"Airing Period: {converted_start_date} - {converted_end_date}"

    airing_details = {
        "airing_period": airing_period,
        "season": season_name,
        "week_id": week_id
    }

    # Return the formatted airing period
    return airing_details