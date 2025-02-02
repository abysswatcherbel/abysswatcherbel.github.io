from praw import Reddit
from praw.models import Submission
from datetime import datetime, timedelta, timezone
import os
import re
import pandas as pd
from pymongo import MongoClient
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.base import ConflictingIdError
from apscheduler.triggers.date import DateTrigger
from apscheduler.jobstores.mongodb import MongoDBJobStore
import logging
from apscheduler.executors.pool import ThreadPoolExecutor, ProcessPoolExecutor
from pytz import utc
from logging.handlers import RotatingFileHandler
from calendar import month_name
from dotenv import load_dotenv

load_dotenv()

# Declare a global variable for the scheduler instance
scheduler_instance = None

def setup_logging(logger: str):
    """Sets up logging with season-based log file storage."""
    today = datetime.now(tz=utc)
    season = get_season_name(today.month)
    month = month_name[today.month]
    log_dir = f"src/logs/{today.year}/{season}/{month}/{today.day}"

    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"{logger}.log")

    file_handler = RotatingFileHandler(log_file, maxBytes=5 * 1024 * 1024, backupCount=3)
    formatter = logging.Formatter(
        "%(asctime)s.%(msecs)03d , %(levelname)s , %(message)s",
        datefmt="%H:%M:%S"
    )
    file_handler.setFormatter(formatter)

    logger_instance = logging.getLogger(logger)
    logger_instance.addHandler(file_handler)
    logger_instance.setLevel(logging.DEBUG if logger == "apscheduler" else logging.INFO)
    logger_instance.propagate = False

    logger_instance.info(f"Logging initialized. Logs will be saved to: {log_file}")
    return logger_instance

def setup_scheduler(mongo_uri=os.getenv('MONGO_URI'), mongo_database="scheduler"):
    """Sets up a scheduler with MongoDB as a job store."""
    client = MongoClient(mongo_uri)
    jobstores = {
        'default': MongoDBJobStore(client=client, database=mongo_database)
    }
    executors = {
        'default': ThreadPoolExecutor(20),
        'processpool': ProcessPoolExecutor(5)
    }
    job_defaults = {
        'coalesce': False,
        'max_instances': 3
    }
    scheduler = BackgroundScheduler(jobstores=jobstores, executors=executors, timezone=utc, job_defaults=job_defaults)
    scheduler.start()

    # Set the global scheduler_instance so that it can be accessed later
    global scheduler_instance
    scheduler_instance = scheduler

    # Only pass the reddit instance as an argument (not the scheduler)
    reddit_instance = setup_reddit_instance()
    scheduler.add_job(
        update_scheduler, 
        'cron', 
        args=[reddit_instance], 
        hour=13, minute=21, 
        name='Daily update'

    )
    return scheduler

def setup_reddit_instance(reddit_id=os.getenv('REDDIT_ID'), reddit_secret=os.getenv('REDDIT_SECRET'), reddit_username=os.getenv('REDDIT_USERNAME')):
    reddit = Reddit(
        client_id=reddit_id,
        client_secret=reddit_secret,
        user_agent=reddit_username,
    )
    return reddit

def update_scheduler(reddit: Reddit):
    """
    This function is scheduled to run daily.
    It fetches new posts and schedules their processing.
    """
    # Get the logger instance for 'close_post'
    logger = logging.getLogger("scheduler")
    # Only set up logging if the logger doesn't already have handlers
    if not logger.handlers:
        logger = setup_logging("scheduler")
    logger.info("Updating scheduler...")
    try:
        new_posts = fetch_recent_posts(reddit=reddit)
        # Use the global scheduler_instance here
        schedule_post_processing(new_posts, reddit, scheduler_instance)
    except Exception as e:
        logger.error(f"Error updating scheduler: {e}", exc_info=True)

def schedule_post_processing(posts: list[dict], reddit: Reddit, scheduler: BackgroundScheduler):
    """
    Schedule the processing of posts 48 hours after their creation.
    """
    # Get the logger instance for 'close_post'
    logger = logging.getLogger("scheduler")
    # Only set up logging if the logger doesn't already have handlers
    if not logger.handlers:
        logger = setup_logging("scheduler")
    
    for post in posts:
        trigger = DateTrigger(run_date=post['closing_at'])
        job_id = f"process_{post['id']}"
        job_name = post.get('title_en')
        
        if scheduler.get_job(job_id):
            continue  # Skip if job already exists
        try:
            scheduler.add_job(
                process_post, 
                trigger=trigger, 
                args=[post, reddit], 
                id=job_id,
                timezone='utc',
                name=job_name
            )
            logger.info(f"Job scheduled for post: {post['id']}")
        except ConflictingIdError:
            logger.warning('Conflicting ID error')
        except Exception as e:
            logger.error(f'Error scheduling job: {e}', exc_info=True)

def process_post(post, reddit):
    """
    Processes a Reddit post: fetches details and inserts them into MongoDB.
    """
    try:
        post_details = close_post(
            post_id=post['id'], 
            reddit=reddit, 
            week_id=post['week_id']
        )
        insert_mongo(post_details)
        print(f"Successfully processed and inserted post: {post['id']}")
    except Exception as e:
        print(f"Error processing post {post['id']}: {e}")

def fetch_recent_posts(reddit: Reddit, username="AutoLovepon", default_tz=timezone.utc):
    user = reddit.redditor(username)
    posts = []
    two_days_ago = datetime.now(tz=default_tz) - timedelta(hours=48)
    for submission in user.submissions.new(limit=100):
        created_time = datetime.fromtimestamp(submission.created_utc, tz=default_tz)
        if created_time > two_days_ago:
            trigger_time = created_time + timedelta(hours=48)
            posts.append({
                'id': submission.id,
                'title': submission.title,
                'created_utc': int(submission.created_utc),
                'closing_at': trigger_time,
                'week_id': get_week_id('episodes', created_time),
                'season': get_season(created_time.month)
            })
    return posts

def close_post(post_id, reddit: Reddit, week_id: int):
    post = Submission(reddit=reddit, id=post_id)
    # Get the logger instance for 'close_post'
    logger = logging.getLogger("close_post")
    # Only set up logging if the logger doesn't already have handlers
    if not logger.handlers:
        logger = setup_logging("close_post")
    title_details, episode = get_title_details(post.title)
    client = MongoClient(os.getenv('MONGO_URI'))
    db = client.anime
    col = db.winter_2025  # Your collection name
    
    romaji = title_details.get("romaji")
    english = title_details.get("english")
    query = {
        "$or": [
            {"title": romaji},
            {"title_english": english},
            {"titles.title": {"$in": [romaji, english]}}
        ]
    }
    mal_doc = col.find_one(query, {"mal_id": 1})
    mal_id = mal_doc["mal_id"] if mal_doc else None

    logger.info(f"Closing post: {post_id} with the MAL ID: {mal_id}")
    
    return {
        "mal_id": mal_id,
        "title": title_details,
        "week_id": week_id,
        "episode": episode,
        "karma": post.score,
        "comments": post.num_comments,
        "upvote_ratio": post.upvote_ratio,
        "post_id": post_id,
        "url": post.url
    }

def insert_mongo(post_details: dict, client: MongoClient = MongoClient(os.getenv('MONGO_URI'))):
    # Get the logger instance for 'close_post'
    logger = logging.getLogger("insert_mongo")
    # Only set up logging if the logger doesn't already have handlers
    if not logger.handlers:
        logger = setup_logging("insert_mongo")
    db = client.anime
    col = db.winter_2025  # Your collection name
    title_info = post_details.get("title", {})
    romaji = title_info.get("romaji")
    english = title_info.get("english")
    mal_id = post_details.get("mal_id")

    episode_data = {
        "week_id": post_details["week_id"],
        "episode": post_details["episode"],
        "karma": post_details["karma"],
        "comments": post_details["comments"],
        "upvote_ratio": post_details["upvote_ratio"],
        "reddit_id": post_details["post_id"],
        "url": post_details["url"]
    }

    logger.info(f"Inserting data into MongoDB for MAL ID: {mal_id}\n{episode_data}")

    if mal_id:
        query = {"mal_id": mal_id}
    else:
        query = {
            "$or": [
                {"title": romaji},
                {"title_english": english},
                {"titles.title": {"$in": [romaji, english]}}
            ]
        }
    if col.find_one(query):
        update_result = col.update_one(
            query,
            {"$push": {"reddit_karma": episode_data}}
        )
        if update_result.upserted_id:
            logger.info(f"Created new document: {update_result.upserted_id}")
        else:
            logger.info("Added entry to existing document")
    else:
        col = db.new_entries
        insert_result = col.insert_one(episode_data)
        logger.info(f"Created new document: {insert_result.upserted_id}")

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
        raise ValueError("Invalid month integer. Please provide a value between 1 and 12.")

def get_season_name(month_int):
    if month_int in range(1, 4):
        return 'winter'
    elif month_int in range(4, 7):
        return 'spring'
    elif month_int in range(7, 10):
        return 'summer'
    elif month_int in range(10, 13):
        return 'fall'
    else:
        raise ValueError("Invalid month integer. Please provide a value between 1 and 12.")

def get_week_id(schedule_type: str = 'episodes', post_time: datetime = datetime.now(timezone.utc)):
    if schedule_type not in ('post', 'episodes'):
        raise ValueError("Invalid schedule_type. Must be either 'post' or 'episodes'.")

    post_day = post_time.date()
    year = post_time.year
    month = post_time.month
    season = get_season_name(month)

    if schedule_type == 'episodes':
        schedule_path = os.path.join('src/season_references', str(year), season, 'episodes.csv')
    else:
        schedule_path = os.path.join('src/season_references', str(year), season, 'post.csv')

    schedule_df = pd.read_csv(schedule_path)
    for _, row in schedule_df.iterrows():
        start_date = datetime.fromisoformat(row['start_date']).date()
        end_date = datetime.fromisoformat(row['end_date']).date()
        if start_date <= post_day <= end_date:
            return row['week_id']
    return None

def get_title_details(title: str):
    romaji_english_pattern = re.compile(r"(.*?)(?: • (.*?))? - Episode (\d+) discussion")
    non_episode_pattern = re.compile(r"(.*?)(?: • (.*?))? - (.*?) Discussion", re.IGNORECASE)
    romaji = ""
    english = ""
    episode = ""
    match = romaji_english_pattern.match(title)
    if match:
        romaji, english, episode = match.groups()
        if not english:
            english = romaji
    else:
        match = non_episode_pattern.match(title)
        if match:
            romaji, english, _ = match.groups()
            if not english:
                english = romaji
    title_details = {
        "romaji": romaji,
        "english": english,
        "original_post": title,
    }
    return title_details, episode

# Example usage
def main():
    for logger_name in ("praw", "prawcore", "pymongo", "apscheduler"):
        setup_logging(logger_name)
    
    # Initialize the scheduler (which sets up the daily update job)
    scheduler = setup_scheduler()
    
    print("Scheduler is running... Press Ctrl+C to exit.")
    try:
        while True:
            pass
    except KeyboardInterrupt:
        print("Shutting down scheduler...")
        scheduler.shutdown()

if __name__ == '__main__':
    main()
