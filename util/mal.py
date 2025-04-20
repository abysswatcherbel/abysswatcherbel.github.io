from pydantic import BaseModel, Field,model_validator, field_validator, ValidationError, PydanticSchemaGenerationError, PydanticUserError, ValidationInfo
from typing import List, Dict, Optional, Any, Union, Annotated
import time
import requests
from util.logger_config import logger
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.errors import PyMongoError
import os
from dotenv import load_dotenv
from datetime import datetime, timezone
load_dotenv()


class MalImages(BaseModel):
    large: Optional[str] = None
    medium: Optional[str] = None


class MalBroadcast(BaseModel):
    day_of_the_week: Optional[str] = None
    start_time: Optional[str] = None


class MalAlternativeTitles(BaseModel):
    synonyms: List[str] = []
    en: Optional[str] = None
    ja: Optional[str] = None


class MalEntity(BaseModel):
    id: int
    name: str


class MalEntry(BaseModel):
    id: int
    url: Optional[str] = None
    images: MalImages
    title: str
    title_english: Optional[str] = None
    media_type: Optional[str] = None
    source: Optional[str] = None
    num_episodes: Optional[int] = None
    status: Optional[str] = None
    score: Optional[float] = None
    members: Optional[int] = None
    season: Optional[str] = None
    year: Optional[int] = None
    start_date: Optional[str] = None
    broadcast: Optional[MalBroadcast] = None
    studios: List[MalEntity] = []
    genres: List[MalEntity] = []
    reddit_karma: Optional[Dict] = None
    streams: Optional[Dict] = None

    @model_validator(mode='before')
    @classmethod
    def transform_mal_node(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        if "node" in data:
            node = data["node"]
        else:
            node = data

        mal_id = node["id"]
        return {
            "id": mal_id,
            "title": node.get("title"),
            "title_english": node.get("alternative_titles", {}).get("en"),
            "images": node.get("main_picture", {}),
            "media_type": node.get("media_type"),
            "source": node.get("source"),
            "num_episodes": node.get("num_episodes"),
            "status": node.get("status"),
            "score": node.get("mean"),  # Optional if included
            "members": node.get("num_list_users"),
            "season": node.get("start_season", {}).get("season"),
            "year": node.get("start_season", {}).get("year"),
            "start_date": node.get("start_date"),
            "broadcast": node.get("broadcast"),
            "studios": node.get("studios", []),
            "genres": node.get("genres", []),
            "url": f'https://myanimelist.net/anime/{mal_id}',
            "reddit_karma": None,
            "streams": None
        }


class JikanTitle(BaseModel):
    type: str
    title: str


class JikanImageFormat(BaseModel):
    image_url: str


class JikanImages(BaseModel):
    jpg: JikanImageFormat


class MalProducer(BaseModel):
    mal_id: int
    url: str
    titles: List[JikanTitle]
    images: JikanImages
    favorites: int
    count: int
    established: str
    country: Optional[str] = None


class MalSeasonals(BaseModel):
    mal_entries: List[MalEntry] = Field(alias="data")


class MalClient:
    BASE_URL = "https://api.myanimelist.net/v2/anime/season"
    ENTRY_URL = "https://api.myanimelist.net/v2/anime"
    JIKAN_BASE_URL = "https://api.jikan.moe/v4"
    HEADERS = {
        "X-MAL-CLIENT-ID": os.getenv('MAL_SECRET'),  # Use OAuth or a static token if allowed
    }

    def __init__(self, year: int = datetime.now(timezone.utc).year, limit: int = 100):
        self.year = year
        self.limit = limit

    def fetch_seasonals(self, season: str, limit_by_members: Optional[int] = None) -> List[MalEntry]:
        url = f"{self.BASE_URL}/{self.year}/{season}"
        params = {
            "limit": self.limit,
            "fields": ",".join([
                "id", "title", "main_picture", "alternative_titles",
                "status", "media_type", "genres", "num_episodes",
                "source", "start_date", "start_season", "broadcast",
                "studios", "num_list_users"
            ]),
            "sort": "num_list_users",
        }

        entries = []
        while url:
            response = requests.get(url, headers=self.HEADERS, params=params)
            response.raise_for_status()
            data = response.json()

            try:
                seasonal = MalSeasonals(**data)
                for entry in seasonal.mal_entries:
                    if limit_by_members is None or (entry.members and entry.members >= limit_by_members):
                        entries.append(entry)
            except ValidationError as e:
                print("Validation error:", e)

            # Pagination
            url = data.get("paging", {}).get("next")
            logger.debug(f"Next URL: {url}")
            params = {}  # MAL requires you to drop query params after the first call with `next` URL

        return entries

    def fetch_entry_by_id(self, mal_id: int) -> Optional[MalEntry]:
        url = f"{self.ENTRY_URL}/{mal_id}"
        params = {
            "fields": ",".join([
                "id", "title", "main_picture", "alternative_titles",
                "status", "media_type", "genres", "num_episodes",
                "source", "start_date", "start_season", "broadcast",
                "studios", "num_list_users", "mean"
            ])
        }

        response = requests.get(url, headers=self.HEADERS, params=params, timeout=10)
        if response.status_code == 404:
            logger.error(f"Entry with ID {mal_id} not found.")
            return None
        elif response.status_code == 403:
            logger.error("Forbidden: Check your MAL API credentials.")
            return None
        elif response.status_code == 429:
            logger.error("Rate limit exceeded. Retrying after 60 seconds...")
            time.sleep(60)
            return self.fetch_entry_by_id(mal_id)
        response.raise_for_status()

        data = {"node": response.json()}
        try:
            return MalEntry(**data)
        except ValidationError as e:
            logger.error("Validation error:", e)
            return None

    def update_score(self, mal_id: int, collection: Collection = None):

        if collection is None:
            client = MongoClient(os.getenv('MONGO_URI'))
            collection = client.anime.seasonals

        logger.info(f'Getting mal_details for id: {mal_id}')

        url = f"{self.ENTRY_URL}/{mal_id}"
        params = {
            "fields": ",".join([
                "id","mean","num_list_users",
            ])
        }

        response = requests.get(url, headers=self.HEADERS, params=params,timeout=90)
        if response.status_code == 200:
            data = response.json()

            collection.update_one(
                {"id": mal_id},
                {"$set": {"score": data.get("mean"), "members": data.get("num_list_users")}},
            )

        else:
            logger.error(f"Error with ID {mal_id}: {response.status_code}")

    def push_to_db(self, mal_entry: MalEntry, collection: Collection = None) -> None:
        """
        Pushes a list of MAL entries to a MongoDB collection.
        
        Args:
            mal_entries: List of MAL entries to push
            collection: MongoDB collection to push to
        """
        if collection == None:
            client = MongoClient(os.getenv('MONGO_URI'))
            collection = client.anime.seasonals

        try:
            entry_dict: Dict = mal_entry.model_dump()
            if collection.find_one({'id': entry_dict['id']}):
                logger.warning(f"Entry with ID {entry_dict['id']} already exists in the database.")
                return
            else:
                collection.insert_one(entry_dict)
                logger.success(f"Pushed {entry_dict['title']} to MongoDB")
        except PydanticSchemaGenerationError as e:
            logger.error(f"Error generating the schema for {mal_entry}: {e}")
            return
        except PyMongoError as e:
            logger.error(f"Error pushing {mal_entry} to MongoDB: {e}")
            return
        except Exception as e:
            logger.error(f"Error pushing {mal_entry} to MongoDB: {e}")
            return

    def fetch_producer_from_jikan(self, mal_id: int):
        url = f"{self.JIKAN_BASE_URL}/producers/{mal_id}"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            data = data.get('data')
            producer = MalProducer(**data)
            return producer
        else:
            logger.error(f"Error fetching producer with ID {mal_id}: {response.status_code}")
            return None

    def fetch_unique_ids(self, season: str, collection: Collection = None) -> List[int]:
        if collection is None:
            client = MongoClient(os.getenv('MONGO_URI'))
            collection = client.anime.seasonals

        try:
            unique_ids = collection.distinct(
                "id", filter={"year": self.year, "season": season}
            )
            return unique_ids
        except PyMongoError as e:
            logger.error(f"Error fetching unique IDs from MongoDB: {e}")
            return []
    
    def update_seasonals_score(self, season: str, collection: Collection = None) -> None:
        if collection is None:
            client = MongoClient(os.getenv('MONGO_URI'))
            collection = client.anime.seasonals

        unique_ids = self.fetch_unique_ids(season, collection)
        for mal_id in unique_ids:
            self.update_score(mal_id, collection)
            time.sleep(0.5)
        logger.info("Updated scores for all entries in the season.")
