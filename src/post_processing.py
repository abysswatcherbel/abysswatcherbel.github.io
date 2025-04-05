"""
Module Overview: post_processing.py

This module serves as the core processor for Reddit discussion posts, particularly those related to anime content. It integrates several key functionalities to automate the lifecycle of a Reddit post, from initial detection and scheduling to final processing and data persistence. The main components and their purposes are as follows:

1. Logging Infrastructure:
   - Provides the function 'setup_logging' to dynamically configure logging for various parts of the application.
   - Organizes log files in a dated directory structure (year/season/month/day) and uses a TimedRotatingFileHandler to enable daily log rotation.
   - Ensures that critical events and errors are captured for debugging and historical analysis.

2. Scheduler Management:
   - Configures a background scheduler via 'setup_scheduler', which uses APScheduler with MongoDB as the job store.
   - Automates the scheduling of tasks such as daily updates and post-processing jobs that close posts after their active period (typically 48 hours).
   - Maintains a global scheduler instance (scheduler_instance) to allow easy access and updates across the module.

3. Reddit API Integration:
   - Sets up a Reddit API client using PRAW through the 'setup_reddit_instance' function.
   - Retrieves recent submissions from a specified user and filters active posts for further processing.
   - Extracts relevant post details and metadata (such as post ID, title, creation timestamp, and associated season/week) needed for later stages in processing.

4. Post Processing Workflow:
   - Implements several functions (fetch_recent_posts, schedule_post_processing, update_scheduler, process_post, close_post) to manage the end-to-end processing of posts.
   - Fetches posts created within the last 48 hours, schedules them for processing after their active engagement period has ended, and processes them to extract final metrics like karma and comment counts.
   - Updates persistent storage (e.g., MongoDB) with the processed data for further analysis or integration with ranking systems.

5. Error Handling and Robustness:
   - Integrates robust error handling, with detailed logging of failures and warnings during post fetching, scheduling, and processing.
   - Ensures that the system continues to operate smoothly even in cases of intermittent failures by logging issues and proceeding with available data.

Overall, post_processing.py is integral to the application's functionality by automating the retrieval, scheduling, and processing of Reddit posts. It bridges multiple subsystems, including logging, scheduling, the Reddit API, and MongoDB, to create a scalable and maintainable pipeline for real-time post analysis.
"""

from praw import Reddit
from praw.models import Submission, Redditor
from datetime import datetime, timedelta, timezone
import os
import json
from math import ceil
import re
from pymongo import MongoClient
import pandas as pd
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.base import ConflictingIdError
from apscheduler.triggers.date import DateTrigger
from apscheduler.jobstores.mongodb import MongoDBJobStore
from apscheduler.executors.pool import ThreadPoolExecutor, ProcessPoolExecutor
from pytz import utc
from dotenv import load_dotenv
from loguru import logger
from util.logger_config import logger
from typing import Dict, List, Tuple, Optional, Union
from util.seasonal_schedule import SeasonScheduler
from util.mal import MalClient


from pydantic import BaseModel, Field, HttpUrl, field_validator, ValidationError


class AnimeTitle(BaseModel):
    """
    Represents the various title formats for an anime.

    Attributes:
        romaji: The romanized Japanese title
        english: The English translated title
        original_post: The original post title from Reddit
    """

    romaji: Optional[str] = None
    english: Optional[str] = None
    original_post: Optional[str] = None

    @field_validator("romaji", "english")
    def title_not_empty(cls, v):
        if v is not None and v.strip() == "":
            return None
        return v


class RedditPostDetails(BaseModel):
    """
    Represents the details of a Reddit discussion post for an anime episode.

    Attributes:
        mal_id: MyAnimeList ID for the anime series
        title: Various title formats for the anime
        week_id: The week number in the current season
        episode: The episode number of the discussed anime
        karma: The Reddit karma (score) of the post
        comments: The number of comments on the post
        upvote_ratio: The ratio of upvotes to total votes
        post_id: The unique Reddit post ID
        url: The URL to the Reddit post
    """

    mal_id: Optional[int] = Field(None, description="MyAnimeList ID for the anime")
    title: AnimeTitle = Field(..., description="Various title formats for the anime")
    week_id: int = Field(..., description="Week number in the season", ge=1, le=13)
    episode: str = Field(..., description="Episode number")
    karma: int = Field(..., description="Reddit post karma score")
    comments: int = Field(..., description="Number of comments on the post")
    upvote_ratio: float = Field(..., description="Upvote ratio", ge=0.0, le=1.0)
    post_id: str = Field(..., description="Reddit post ID")
    url: str = Field(..., description="Reddit post URL")


class KarmaEntry(RedditPostDetails):
    """
    Extended model for karma tracking entries that includes additional metadata.

    This model extends RedditPostDetails to include additional fields needed
    for tracking and comparing karma across episodes and seasons.

    Attributes:
        mal_stats: Optional MAL statistics for the anime
        rank: Current rank in karma charts
        rank_change: Change in rank compared to previous episode
        karma_change: Change in karma compared to previous episode
    """

    mal_stats: Optional[Dict] = Field(None, description="MAL statistics")
    rank: Optional[int] = Field(None, description="Current rank in karma charts")
    rank_change: Optional[Union[int, str]] = Field(
        None, description="Change in rank (int or 'new'/'returning')"
    )
    karma_change: Optional[int] = Field(
        None, description="Change in karma from previous episode"
    )


class SeasonalKarmaCollection(BaseModel):
    """
    Collection of karma entries for a season.

    Attributes:
        season: The season name (winter, spring, summer, fall)
        year: The year
        week: The week number in the season
        entries: List of karma entries
    """

    season: str = Field(..., description="Season name")
    year: int = Field(..., description="Year")
    week: int = Field(..., description="Week number", ge=1, le=13)
    entries: List[KarmaEntry] = Field(..., description="List of karma entries")


load_dotenv()

# Declare a global variable for the scheduler instance
scheduler_instance = None


def setup_scheduler(mongo_uri=os.getenv("MONGO_URI"), mongo_database="scheduler"):
    """
    Sets up a scheduler with MongoDB as a job store.

    This function creates a scheduler instance that uses MongoDB as its job store.
    It also sets up the executors and job defaults for the scheduler.

    Args:
        mongo_uri (str): The MongoDB connection URI
        mongo_database (str): The MongoDB database name

    Returns:
        BackgroundScheduler: A scheduler instance configured with MongoDB job store
    """

    client = MongoClient(mongo_uri)
    jobstores = {"default": MongoDBJobStore(client=client, database=mongo_database)}
    executors = {
        "default": ThreadPoolExecutor(10),
        "processpool": ProcessPoolExecutor(3),
    }
    job_defaults = {"coalesce": False, "max_instances": 3}
    scheduler = BackgroundScheduler(
        jobstores=jobstores,
        executors=executors,
        timezone=utc,
        job_defaults=job_defaults,
        misfire_grace_time=42600,  # 12 hours + 1 minute
    )
    scheduler.start()

    # Set the global scheduler_instance so that it can be accessed later
    global scheduler_instance
    scheduler_instance = scheduler

    # Only pass the reddit instance as an argument (not the scheduler)
    reddit_instance = setup_reddit_instance()
    update_scheduler(reddit_instance)
    job_id = "daily_update"

    if not scheduler.get_job(job_id):
        # Skip if job already exist
        scheduler.add_job(
            update_scheduler,
            "cron",
            args=[reddit_instance],
            hour=23,
            minute=00,
            name="Daily update",
            id="daily_update",
        )
    if scheduler:
        logger.success("Scheduler setup completed")
    else:
        logger.error("Scheduler setup failed")
    return scheduler


def setup_reddit_instance(
    reddit_id=os.getenv("REDDIT_ID"),
    reddit_secret=os.getenv("REDDIT_SECRET"),
    reddit_username=os.getenv("REDDIT_USERNAME"),
) -> Reddit:
    """
    Sets up a Reddit API instance using the provided credentials.

    This function initializes a Reddit API instance with the specified client ID,
    client secret, and user agent. It is used to interact with Reddit through the
    PRAW library.

    Args:
        reddit_id (str): The Reddit client ID
        reddit_secret (str): The Reddit client secret
        reddit_username (str): The Reddit username

    Returns:
        Reddit: A Reddit API instance

    Example:
        >>> reddit = setup_reddit_instance()
        >>> print(reddit.user.me())
        <Redditor u/AutoLovepon>
    """
    # log = setup_logging("reddit")

    reddit = Reddit(
        client_id=reddit_id,
        client_secret=reddit_secret,
        user_agent=reddit_username,
    )

    logger.info("Reddit instance initialized")
    return reddit


def update_scheduler(reddit: Reddit) -> None:
    """
    Updates the scheduler with new Reddit discussion posts.

    This function fetches recent discussion posts and schedules them for processing after their
    48-hour active period. It is called both on startup and via a daily scheduled job to ensure
    all new posts are properly tracked and processed.

    Args:
        reddit (Reddit): An authenticated Reddit API instance for interacting with Reddit.

    Returns:
        None

    Raises:
        Exception: Any errors during post fetching or scheduler updates are logged and propagated.

    Example:
        >>> reddit = setup_reddit_instance()
        >>> update_scheduler(reddit)
        # Fetches new posts and schedules them for processing
    """
    # log = setup_logging("scheduler")
    logger.info("Updating scheduler...")

    try:
        new_posts = fetch_recent_posts(reddit=reddit)
        # Use the global scheduler_instance here
        schedule_post_processing(new_posts, reddit, scheduler_instance)
    except Exception as e:
        logger.error(f"Error updating scheduler: {e}", exc_info=True)


def schedule_post_processing(
    posts: list[dict], reddit: Reddit, scheduler: BackgroundScheduler
) -> None:
    """
    Schedule post processing jobs for a list of Reddit discussion posts.

    This function takes a list of posts and schedules them for processing after their
    48-hour active period ends. For each post, it creates a job that will run at the
    specified closing time to process the final state of the post.

    Args:
        posts (list[dict]): A list of dictionaries containing post details. Each dict should have:
            - "id" (str): The Reddit post ID
            - "closing_at" (datetime): When the post should be processed
            - "title_en" (str): English title of the anime (used for job name)
        reddit (Reddit): An authenticated Reddit API instance
        scheduler (BackgroundScheduler): The scheduler instance to add jobs to

    Returns:
        None

    Raises:
        ConflictingIdError: If a job with the same ID already exists
        Exception: For any other errors during job scheduling
    """
    # log = setup_logging("scheduler")

    for post in posts:
        trigger = DateTrigger(run_date=post["closing_at"])
        job_id = f"process_{post['id']}"
        job_name = post.get("title_en")

        if scheduler.get_job(job_id):
            logger.warning(f"Job {job_id} already exists, skipping...")
            continue  # Skip if job already exists
        try:
            scheduler.add_job(
                process_post,
                trigger=trigger,
                args=[post, reddit],
                id=job_id,
                timezone="utc",
                name=job_name,
            )
            logger.success(f"Job scheduled for post: {post['id']}")
        except ConflictingIdError:
            logger.warning(f"Conflicting ID error for job: {job_id}")
        except Exception as e:
            logger.error(f"Error scheduling job: {e}", exc_info=True)


def process_post(post: Dict, reddit: Reddit) -> None:
    """
    Process a Reddit post by closing it and storing its details in MongoDB.

    This function handles the processing of a Reddit discussion post, which involves:
    1. Closing the post after the 48 hours (retrieving final karma/comment counts)
    2. Storing the post details in MongoDB

    The function uses error handling to gracefully handle any issues during processing
    and logs all significant events.

    Args:
        post (dict): A dictionary containing post details with the following keys:
            - "id" (str): The Reddit post ID
            - "week_id" (int): The identifier for the week
        reddit (Reddit): An authenticated instance of the Reddit API client

    Returns:
        None

    Raises:
        Exception: Any unexpected errors during post processing are caught and logged
    """
    

    try:
        logger.debug(f"Processing post received from scheduler: {post}")
        post_details: Dict = close_post(
            post_id=post["id"], reddit=reddit, week_id=post["week_id"]
        )
        if not post_details:
            logger.error(f"Post {post['id']} is not available")
            return
        logger.debug(f"Trying to insert post: {json.dumps(post_details, indent=2)}")
        try:
            post_validation = RedditPostDetails(**post_details)
            insert_mongo(post_validation.model_dump())
            logger.success(f"Successfully processed and inserted post: {post_validation.model_dump_json(indent=2)}")
        except ValidationError as e:
            logger.error(f"Validation error for post {post['id']}: {e}")
    except Exception as e:
        logger.error(f"Error processing post {post['id']}: {e}")


def fetch_recent_posts(reddit: Reddit, username="AutoLovepon") -> List[Dict]:
    """
    Retrieves recent Reddit posts submitted by AutoLovepon (The r/anime bot) within the last 48 hours.

    This function fetches the latest submissions from the user and filters them to include only those
    created within the past 48 hours. For each relevant submission, it compiles essential details such as the post ID,
    title, creation time, scheduled closing time, associated week ID, and season. The collected posts are returned
    as a list of dictionaries for further processing.

    Args:
        reddit (Reddit): An instance of the Reddit API client from the PRAW library.
        username (str, optional): The Reddit username whose posts are to be fetched. Defaults to "AutoLovepon".
        default_tz (timezone, optional): The timezone to be used for datetime operations. Defaults to UTC.

    Returns:
        list[dict]: A list of dictionaries, each containing details of a Reddit post. Each dictionary includes:
            - "id" (str): The unique identifier of the Reddit post.
            - "title" (str): The title of the Reddit post.
            - "created_utc" (int): The UTC timestamp of when the post was created.
            - "closing_at" (datetime): The scheduled time to close the post, set to 48 hours after creation.
            - "week_id" (int): The identifier for the week associated with the post, determined by the creation time.
            - "season" (str): The season (e.g., winter, spring) determined by the creation month.

    Raises:
        praw.exceptions.PRAWException: If there is an issue interacting with the Reddit API.
        Exception: For any unexpected errors that occur during the fetching and processing of posts.

    Examples:
        >>> reddit_instance = Reddit(client_id='my_id', client_secret='my_secret', user_agent='my_agent')
        >>> recent_posts = fetch_recent_posts(reddit_instance, username="AutoLovepon")
        >>> for post in recent_posts:
        ...     print(post['title'], post['closing_at'])
        ...
        "Kusuriya no Hitorigoto • The Apothecary Diaries - Episode 3 discussion" 2024-04-27 15:30:00+00:00
        "Another Anime Discussion Topic" 2024-04-28 12:45:00+00:00
    """
    # log = setup_logging("fetch_posts")
    logger.info(f"Fetching recent posts from user: {username}")

    user: Redditor = reddit.redditor(username)
    posts = []
    two_days_ago: datetime = datetime.now(timezone.utc) - timedelta(hours=48)
    submissions: List[Submission] = user.submissions.new(limit=100)
    for submission in submissions:
        created_time: datetime = datetime.fromtimestamp(
            submission.created_utc, tz=timezone.utc
        )
        if created_time > two_days_ago:
            season_scheduler = SeasonScheduler(post_time=created_time)
            trigger_time = created_time + timedelta(hours=48)
            logger.debug(f"Trigger set for post: {submission.url} at {trigger_time}")
            posts.append(
                {
                    "id": submission.id,
                    "title": submission.title,
                    "created_utc": int(submission.created_utc),
                    "closing_at": trigger_time,
                    "week_id": season_scheduler.week_id,
                    "season": season_scheduler.season_name,
                }
            )
    if posts:
        logger.info(f"Found {len(posts)} posts within the last 48 hours")
    else:
        logger.warning("No posts found within the last 48 hours")
    return posts


def check_post_status(submission: Submission, post_id: str) -> bool:
    """
    Checks the status of a Reddit discussion post.

    This function verifies if a Reddit post is still available and accessible by checking
    various status indicators such as whether it has been removed, deleted, or hidden.

    Args:
        submission (Submission): The PRAW Submission object representing the Reddit post.
        post_id (str): The unique identifier of the Reddit post.

    Returns:
        bool: True if the post is still available and accessible, False otherwise.

    Raises:
        Exception: If there is an error fetching the post status.

    Example:
        >>> reddit = Reddit(...)
        >>> submission = reddit.submission(id='abc123')
        >>> check_post_status(submission, 'abc123')
        True
    """
    # log = setup_logging("check_post_status")

    try:
        if submission.removed_by_category:
            logger.warning(
                f"Post {post_id} was removed by moderators: {submission.removed_by_category}"
            )
            return False
        elif submission.selftext == "[deleted]":
            logger.warning(f"Post {post_id} was deleted by the user.")
            return False
        elif submission.selftext == "[removed]":
            logger.warning(f"Post {post_id} was removed by moderators.")
            return False
        elif submission.hidden:
            logger.warning(f"Post {post_id} is hidden by the user.")
            return False
        else:
            logger.info(f"Post {post_id} is still available.")
            return True
    except Exception as e:
        logger.error(f"Error fetching post: {e}")
        return False


def close_post(post_id, reddit: Reddit, week_id: int) -> Dict:
    """
    Processes and closes a Reddit discussion post after its active period.

    This function retrieves the final state of a Reddit discussion post (karma, comments, etc.)
    after its 48-hour active period has ended. It validates the post's availability and
    extracts relevant metadata including MAL ID and episode number.

    Args:
        post_id (str): The Reddit post ID to process
        reddit (Reddit): An authenticated Reddit API instance
        week_id (int): The week number for seasonal tracking purposes

    Returns:
        dict: A dictionary containing the post's final state and metadata including:
            - mal_id: MyAnimeList ID for the anime
            - title: Dictionary with romaji and english titles
            - week_id: Week number in the season
            - episode: Episode number
            - karma: Final karma score
            - comments: Total comment count
            - upvote_ratio: Final upvote ratio
            - post_id: Reddit post ID
            - url: Full Reddit post URL

    Raises:
        No explicit exceptions, but logs any errors encountered during processing
    """
    post = Submission(reddit=reddit, id=post_id)
    # log = setup_logging("close_post")

    post_available = check_post_status(post, post_id)
    if not post_available:
        return {}

    mal_id = get_mal_id_reddit_post(
        post.selftext
    )  # Try to get the MAL id from the body of the post
    title_details, episode = get_title_details(post.title)
    if not week_id:
        week_id = SeasonScheduler(
            post_time=datetime.fromtimestamp(post.created_utc, tz=timezone.utc)
        ).week_id
    client = MongoClient(os.getenv("MONGO_URI"))
    db = client.anime
    col = db.seasonals

    romaji = title_details.get("romaji")
    english = title_details.get("english")

    # If no MAL ID is found, try to the entry from the title
    query = (
        {"id": mal_id}
        if mal_id
        else {"$or": [{"title": romaji}, {"title_english": english}]}
    )
    logger.debug(f"Looking for entry on the db with: {json.dumps(query, indent=2)}")
    mal_doc = col.find_one(query, {"id": 1})  # Check if the show exists on the db

    # If there is a mal_id but no document found, try to fetch the entry from MAL and push it to the db
    if mal_id and not mal_doc:
        logger.warning(
            f"Post {post_id} has a MAL ID but no document found in the database. Fetching it and pushing it to the db..."
        )
        try:
            mal = MalClient()
            entry = mal.fetch_entry_by_id(mal_id)
            if entry:
                mal.push_to_db(entry)
                logger.success(
                    f"Fetched and pushed entry from the post {post_id} with the MAL ID {mal_id} to the database."
                )
        except Exception as e:
            logger.error(
                f"Error fetching MAL entry for post id {mal_id} and from the post {post_id}: {e}"
            )

    post_details = {
        "mal_id": mal_id,
        "title": title_details,
        "week_id": week_id,
        "episode": episode,
        "karma": post.score,
        "comments": post.num_comments,
        "upvote_ratio": post.upvote_ratio,
        "post_id": post_id,
        "url": post.url,
    }

    logger.debug(f"Post details: {json.dumps(post_details, indent=2)}")

    return post_details


def insert_mongo(
    post_details: dict,
    client: MongoClient = MongoClient(os.getenv("MONGO_URI")),
    schedule=SeasonScheduler(),
) -> None:
    """
    Inserts post details into the MongoDB database.

    This function processes the provided post details and inserts them into the appropriate MongoDB collections.
    If a document with the specified MAL ID exists in the season collection, it appends the new karma data
    to the existing `reddit_karma` array. If the MAL ID does not exist, it creates a new document in the
    `new_entries` collection.

    Args:
        post_details (dict): A dictionary containing the details of the Reddit post. Expected keys include:
            - "week_id" (int): The identifier for the week.
            - "episode" (str): The episode number.
            - "karma" (int): The karma score of the post.
            - "comments" (int): The number of comments on the post.
            - "upvote_ratio" (float): The upvote ratio of the post.
            - "post_id" (str): The Reddit post ID.
            - "url" (str): The URL of the post.
            - "title" (dict): A dictionary containing title information with keys "romaji" and "english".
            - "mal_id" (int or None): The MyAnimeList ID associated with the post.

        client (MongoClient, optional): An instance of MongoClient for connecting to MongoDB.
                                         Defaults to a new client using the `MONGO_URI` environment variable.

    Raises:
        KeyError: If essential keys are missing from `post_details`.
        Exception: For any unexpected errors during database operations.

    Returns:
        None
    """

    # Get the database and collection
    db = client.anime
    col = db.seasonals

    # Get the title details
    mal_id = post_details.get("mal_id") or post_details.get("id")
    reddit_id = post_details.get("post_id")

    episode_data = {
        "week_id": post_details["week_id"],
        "episode": post_details["episode"],
        "karma": post_details["karma"],
        "comments": post_details["comments"],
        "upvote_ratio": post_details["upvote_ratio"],
        "reddit_id": reddit_id,
        "url": post_details["url"],
    }

    logger.info(
        f"Inserting data into MongoDB for MAL ID: {json.dumps(mal_id, indent=2)}"
    )
    query = {"id": mal_id}
    show = col.find_one(query)

    if show:
        year_str = str(schedule.year)
        season_name = schedule.season_name

        # Handle the reddit_karma structure properly to support multiple years and seasons

        # Check if the document has the reddit_karma field
        if "reddit_karma" not in show:
            # Initialize the reddit_karma object if it doesn't exist
            col.update_one(query, {"$set": {"reddit_karma": {}}})
            show = col.find_one(query)  # Refresh the data

        # Check if the year exists in reddit_karma
        if year_str not in show.get("reddit_karma", {}):
            # Initialize the year as an empty object if it doesn't exist
            col.update_one(query, {"$set": {f"reddit_karma.{year_str}": {}}})
            show = col.find_one(query)  # Refresh the data

        # Check if the season exists in the year
        if season_name not in show.get("reddit_karma", {}).get(year_str, {}):
            # Initialize the season as an empty array if it doesn't exist
            col.update_one(
                query, {"$set": {f"reddit_karma.{year_str}.{season_name}": []}}
            )

        # Now push the episode data to the season array
        update_path = f"reddit_karma.{year_str}.{season_name}"
        update_result = col.update_one(query, {"$push": {update_path: episode_data}})

        logger.info(
            f"Updated {update_result.modified_count} documents with {mal_id} | {show.get('title_english')}"
        )
    else:
        if mal_id:
            logger.warning(
                f"Document with MAL ID {mal_id} not found. Trying to fetch from MAL api and create a new entry..."
            )
            try:
                mal = MalClient()
                entry = mal.fetch_entry_by_id(mal_id)
                if entry:
                    mal.push_to_db(entry)
                    logger.success(
                        f"Fetched and pushed entry from the post {reddit_id} with the MAL ID {mal_id} to the database."
                    )

                    # After creating the entry, add the karma data with the proper structure
                    show = col.find_one(query)
                    if show:
                        year_str = str(schedule.year)
                        season_name = schedule.season_name

                        # Properly initialize the nested structure
                        reddit_karma = {}
                        reddit_karma[year_str] = {}
                        reddit_karma[year_str][season_name] = [episode_data]

                        col.update_one(query, {"$set": {"reddit_karma": reddit_karma}})
                        logger.info(
                            f"Added karma data to newly created entry for MAL ID {mal_id}"
                        )
            except Exception as e:
                logger.error(
                    f"Error fetching MAL entry for post id {mal_id} and from the post {reddit_id}: {e}"
                )
        else:
            logger.warning(
                f"Post {reddit_id} has no MAL ID. Cannot create a new entry on the default db"
            )

            col = db.new_entries
            insert_result = col.insert_one(episode_data)
            logger.warning(
                f"Created new document: for the post {reddit_id} MAL ID: {mal_id} with the ID: {insert_result.inserted_id}"
            )


def get_title_details(title: str) -> Tuple[Dict, str]:
    """
    Extracts romaji and English titles along with the episode number from the r/anime post title.

    This function utilizes regular expressions to parse the title, extracting the romaji
    (Japanese), English titles, and the episode number if present. It handles titles with and without
    episode information, ensuring that the English title defaults to the romaji title when the English
    translation is not provided.

    Args:
        title (str): The title of the Reddit post to be parsed.

    Returns:
        tuple:
            - title_details (dict): A dictionary containing:
                - "romaji" (str): The romaji (Japanese Romantic title) of the anime.
                - "english" (str): The English title of the anime. Defaults to romaji if not provided.
                - "original_post" (str): The original title of the Reddit post.
            - episode (str): The episode number extracted from the title. Returns an empty string if not found.

    Raises:
        None

    Examples:
        >>> get_title_details("Kusuriya no Hitorigoto • The Apothecary Diaries - Episode 3 discussion")
        (
            {
                "romaji": "Kusuriya no Hitorigoto",
                "english": "The Apothecary Diaries",
                "original_post": "Kusuriya no Hitorigoto • The Apothecary Diaries - Episode 3 discussion"
            },
            "3"
        )

        >>> get_title_details("Kusuriya no Hitorigoto - Movie Discussion")
        (
            {
                "romaji": "Kusuriya no Hitorigoto",
                "english": "Kusuriya no Hitorigoto",
                "original_post": "Kusuriya no Hitorigoto - Movie Discussion"
            },
            ""
        )
    """

    romaji_english_pattern = re.compile(
        r"(.*?)(?: • (.*?))? - Episode (\d+) discussion"
    )
    non_episode_pattern = re.compile(
        r"(.*?)(?: • (.*?))? - (.*?) Discussion", re.IGNORECASE
    )
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


def get_active_posts(
    reddit: Reddit = setup_reddit_instance(),
    username="AutoLovepon",
    default_tz=timezone.utc,
) -> List:
    """
    Retrieves active discussion posts on r/anime for the karma ranking system.

    For our purposes, a post is considered active if it falls within the first 48 hours of posting.
    This active period is critical because it reflects the window of highest engagement,
    which we use to gauge the post's performance in terms of karma.

    Parameters:
        reddit (Reddit): An authenticated Reddit API instance, defaulting to the one provided by setup_reddit_instance().
        username (str): The Reddit username whose posts are to be fetched. Defaults to "AutoLovepon".
        default_tz (timezone): The timezone to be used for datetime calculations. Defaults to UTC.

    Returns:
        list[dict]: A list of dictionaries, each containing details of an active post.

    Raises:
        Exception: Any issues encountered while fetching or processing posts will be propagated.

    Note:
        This function filters for submissions made within the past 48 hours,
        ensuring only those posts in the active discussion period are returned.
    """
    # log = setup_logging("hourly_data")

    user = reddit.redditor(username)
    client = MongoClient(os.getenv("MONGO_URI"))
    db = client.anime
    seasonals = db.seasonals
    hourly_data = db.karma_watch
    posts = []
    current_time = datetime.now(tz=default_tz)
    two_days_ago = current_time - timedelta(hours=48)
    schedule = SeasonScheduler()

    # Get the submissions from AutoLovePon
    for submission in user.submissions.new(limit=50):

        # The time the submission was created should be in datetime format
        created_time = datetime.fromtimestamp(submission.created_utc, tz=default_tz)

        # Check if the submission was created within the last 48 hours
        if created_time > two_days_ago:
            trigger_time = created_time + timedelta(hours=48)
            time_left = trigger_time - current_time
            hours_since_post = current_time - created_time

            # Try to get a valid mal_id from the post body
            mal_id = get_mal_id_reddit_post(submission.selftext)

            # Try to get the number of the episode from the title
            _, episode = get_title_details(submission.title)

            # If there is a mal_id, try to get the series details from the db
            if mal_id:
                try:
                    mal_id = int(mal_id)
                    show = None
                    show = seasonals.find_one(
                        {"id": mal_id},
                        {
                            "_id": 0,
                            "title": 1,
                            "streams": 1,
                            "title_english": 1,
                            "mal_id": "$id",
                            "images": 1,
                            "broadcast": 1,
                        },
                    )

                    # If there is a valid mal_id but no document found, try to fetch the entry from MAL and push it to the db
                    if not show:
                        logger.warning(
                            f"Post {submission.id} has a MAL ID but no document found in the database."
                        )
                        try:
                            mal = MalClient()
                            entry = mal.fetch_entry_by_id(mal_id)
                            if entry:
                                mal.push_to_db(entry)
                                logger.success(
                                    f"Fetched and pushed entry from the post {submission.id} with the MAL ID {mal_id} to the database."
                                )
                                show = seasonals.find_one(
                                    {"id": mal_id},
                                    {
                                        "_id": 0,
                                        "title": 1,
                                        "streams": 1,
                                        "title_english": 1,
                                        "mal_id": "$id",
                                        "images": 1,
                                        "broadcast": 1,
                                    },
                                )
                        except Exception as e:
                            logger.error(
                                f"Error fetching MAL entry for post id {mal_id} and from the post {submission.id}: {e}"
                            )
                            continue
                    else:

                        post_details = dict(show)
                        post_details["reddit_url"] = submission.url
                        post_details["karma"] = submission.score
                        post_details["comments"] = submission.num_comments
                        # Time left in hours
                        post_details["time_left"] = time_left.total_seconds() / 3600

                        posts.append(post_details)

                        # Round the hour since post to nearest hour
                        hour = round(hours_since_post.total_seconds() / 3600, 0)
                        karma = submission.score

                        # Check if document for this mal_id and reddit_id exists
                        existing_doc = hourly_data.find_one(
                            {"mal_id": mal_id, "reddit_id": submission.id}
                        )

                        if existing_doc:
                            # Document exists, check if this hour already exists in hourly_karma
                            hour_exists = any(
                                entry.get("hour") == hour
                                for entry in existing_doc.get("hourly_karma", [])
                            )

                            if hour_exists:
                                # Hour exists, update the karma value for this hour
                                hourly_data.update_one(
                                    {
                                        "mal_id": mal_id,
                                        "reddit_id": submission.id,
                                        "hourly_karma.hour": hour,
                                    },
                                    {
                                        "$set": {
                                            "updated_at": current_time.strftime(
                                                "%Y-%m-%d %H:%M:%S"
                                            ),
                                            "hourly_karma.$.karma": karma,
                                        }
                                    },
                                )

                            else:
                                # Hour doesn't exist, push new entry
                                hourly_data.update_one(
                                    {"mal_id": mal_id, "reddit_id": submission.id},
                                    {
                                        "$set": {
                                            "updated_at": current_time.strftime(
                                                "%Y-%m-%d %H:%M:%S"
                                            )
                                        },
                                        "$push": {
                                            "hourly_karma": {
                                                "hour": hour,
                                                "karma": karma,
                                            }
                                        },
                                    },
                                )

                        else:
                            # Document doesn't exist, create a new one
                            hourly_data.insert_one(
                                {
                                    "mal_id": mal_id,
                                    "reddit_id": submission.id,
                                    "week_id": schedule.week_id,
                                    "season": schedule.season_name,
                                    "year": schedule.year,
                                    "title": show.get("title"),
                                    "title_english": show.get("title_english"),
                                    "episode": episode,
                                    "created_at": current_time.strftime(
                                        "%Y-%m-%d %H:%M:%S"
                                    ),
                                    "updated_at": current_time.strftime(
                                        "%Y-%m-%d %H:%M:%S"
                                    ),
                                    "hourly_karma": [{"hour": hour, "karma": karma}],
                                }
                            )
                            logger.info(
                                f"Created new hourly tracking for MAL ID {mal_id}, post {submission.id}"
                            )

                except ValueError:
                    logger.error(f"Error updating hourly data for MAL ID: {mal_id}")
                    continue
            else:
                logger.error(f"No MAL ID found for post: {submission.id}")
                continue
    client.close()
    return posts


def get_mal_id_reddit_post(post_body: str) -> Optional[str]:
    """
    Extracts the MyAnimeList ID from a Reddit post body.

    This function searches for a MyAnimeList URL in the post body text and extracts
    the anime ID from it. The URL is expected to be in the format:
    'https://myanimelist.net/anime/[ID]'

    Args:
        post_body (str): The body text of the Reddit post containing the MAL URL.

    Returns:
        str or None: The extracted MyAnimeList ID if found, None otherwise.

    Example:
        >>> body = "Check out this anime: https://myanimelist.net/anime/12345"
        >>> get_mal_id_reddit_post(body)
        '12345'
    """
    mal_url = re.search(r"https://myanimelist.net/anime/(\d+)", post_body)
    mal_id = mal_url.group(1) if mal_url else None
    try:
        mal_id = int(mal_id)
    except ValueError:
        logger.error(f"Error converting MAL ID to integer: {mal_id}")
        mal_id = None
    return mal_id


def fetch_weekly_posts_db(
    schedule: SeasonScheduler = SeasonScheduler(schedule_type="post"),
):
    """Fetch MAL IDs of all shows airing in the current week."""
    client = MongoClient(os.getenv("MONGO_URI"))
    db = client.anime
    seasonal_entries = db.seasonals

    # Determine current week
    current_week = schedule.week_id
    current_year = schedule.year
    current_season = schedule.season_name

    reddit_karma = f"reddit_karma.{current_year}.{current_season}"
    current_data = list(
        seasonal_entries.aggregate(
            [
                {"$unwind": f"${reddit_karma}"},
                {"$match": {f"{reddit_karma}.week_id": current_week}},
                {
                    "$project": {
                        "_id": 0,
                        "id": 1,
                        "title": 1,
                        "title_english": 1,
                        "episode": f"${reddit_karma}.episode",
                        "karma": f"${reddit_karma}.karma",
                        "comments": f"${reddit_karma}.comments",
                        "week_id": f"${reddit_karma}.week_id",
                        "url": f"${reddit_karma}.url",
                        "num_episodes": 1,
                    }
                },
            ]
        )
    )

    client.close()
    return current_data


def fetch_weekly_posts_reddit(
    reddit: Reddit = setup_reddit_instance(),
    schedule: SeasonScheduler = SeasonScheduler(),
    username="AutoLovepon",
    default_tz=timezone.utc,
):
    user = reddit.redditor(username)
    posts = []
    week_id = schedule.week_id - 1 if datetime.now().weekday() in (4,5,6) else schedule.week_id
    # Get the current week schedule
    schedule_details = schedule.get_schedule_for_date(
        year=schedule.year, season=schedule.season_number, week_id=week_id
    )
    if schedule_details:
        start_date = schedule_details.start_date
        end_date = schedule_details.end_date
        for submission in user.submissions.new(limit=100):
            created_time = datetime.fromtimestamp(submission.created_utc, tz=default_tz)
            if created_time >= start_date and created_time <= end_date:
                title_details, episode = get_title_details(submission.title)

                posts.append(
                    {
                        "id": get_mal_id_reddit_post(submission.selftext),
                        "reddit_id": submission.id,
                        "title": title_details.get("romaji"),
                        "title_english": title_details.get("english"),
                        "episode": episode,
                        "created_utc": int(submission.created_utc),
                        "week_id": week_id,
                        "karma": submission.score,
                        "comments": submission.num_comments,
                        "upvote_ratio": submission.upvote_ratio,
                        "url": submission.url,
                    }
                )
        if posts:

            return posts
        else:
            return []
    else:
        return


def missing_shows_on_db(shows_reddit: List[Dict], shows_db: List[Dict]) -> List:
    """
    Compare shows from Reddit against shows in the database to find which ones are missing.

    Args:
        shows_reddit: List of show dictionaries from Reddit
        shows_db: List of show dictionaries from the database

    Returns:
        List of dictionaries representing shows that appear on Reddit but not in the database
    """
    # Create DataFrames from the lists
    reddit_df = pd.DataFrame(shows_reddit)
    db_df = pd.DataFrame(shows_db)

    # Handle empty dataframes
    if reddit_df.empty:
        return []

    if db_df.empty:
        return shows_reddit

    # Filter out shows where id is None or NaN
    reddit_df = reddit_df.dropna(subset=["id"])

    # Get the set of show IDs from each source
    reddit_ids = set(reddit_df["id"].astype(str))
    db_ids = set(db_df["id"].astype(str))

    # Find IDs that are in Reddit but not in the database
    missing_ids = reddit_ids - db_ids

    # Filter the reddit_df to only include rows with the missing IDs
    missing_shows = reddit_df[reddit_df["id"].astype(str).isin(missing_ids)].to_dict(
        "records"
    )

    return missing_shows


# Example usage
def main():

    # Initialize the scheduler (which sets up the daily update job)
    scheduler = setup_scheduler()

    print("Scheduler is running... Press Ctrl+C to exit.")
    try:
        while True:
            pass
    except KeyboardInterrupt:
        print("Shutting down scheduler...")
        scheduler.shutdown()
