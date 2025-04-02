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
   

class MalSeasonals(BaseModel):
    mal_entries: List[MalEntry] = Field(alias="data")


class MalClient:
    BASE_URL = "https://api.myanimelist.net/v2/anime/season"
    ENTRY_URL = "https://api.myanimelist.net/v2/anime"
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

        response = requests.get(url, headers=self.HEADERS, params=params)
        if response.status_code == 404:
            logger.error(f"Entry with ID {mal_id} not found.")
            return None
        response.raise_for_status()

        data = {"node": response.json()}
        try:
            return MalEntry(**data)
        except ValidationError as e:
            logger.error("Validation error:", e)
            return None
    
    def push_to_db(self, mal_entry: MalEntry, collection: Collection = None) -> None:
        """
        Pushes a list of MAL entries to a MongoDB collection.
        
        Args:
            mal_entries: List of MAL entries to push
            collection: MongoDB collection to push to
        """
        if not collection:
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


