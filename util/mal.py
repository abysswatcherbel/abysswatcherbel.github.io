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
    media_type: str
    source: str
    num_episodes: Optional[int] = None
    status: str
    score: Optional[float] = None
    members: Optional[int] = None
    season: Optional[str] = None
    year: Optional[int] = None
    start_date: Optional[str] = None
    broadcast: Optional[MalBroadcast] = None
    studios: List[MalEntity] = []
    genres: List[MalEntity] = []
    reddit_karma: Optional[int] = None
    streams: Optional[List[MalEntity]] = None

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
            "title": node["title"],
            "title_english": node.get("alternative_titles", {}).get("en") or None,
            "images": node.get("main_picture", {}),
            "media_type": node["media_type"],
            "source": node["source"],
            "num_episodes": node.get("num_episodes"),
            "status": node["status"],
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

    def __init__(self, year: int, limit: int = 100):
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
            ])
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
            params = {}  # MAL requires you to drop query params after the first call with `next` URL

        return entries

    def fetch_entry_by_id(self, mal_id: int) -> Optional[MalEntry]:
        url = f"{self.ENTRY_URL}/{mal_id}"
        params = {
            "fields": ",".join([
                "id", "title", "main_picture", "alternative_titles",
                "status", "media_type", "genres", "num_episodes",
                "source", "start_date", "start_season", "broadcast",
                "studios", "num_list_users"
            ])
        }

        response = requests.get(url, headers=self.HEADERS, params=params)
        if response.status_code == 404:
            return None
        response.raise_for_status()

        data = {"node": response.json()}
        try:
            return MalEntry(**data)
        except ValidationError as e:
            print("Validation error:", e)
            return None



def fetch_mal_seasonals(year: int, season: str) -> MalSeasonals:
    """
    Fetches all anime from a specific year and season from MyAnimeList,
    handling pagination and rate limits.
    
    Args:
        year: The year to fetch anime for
        season: The season to fetch anime for (spring, summer, fall, winter)
        
    Returns:
        MalSeasonals object containing all entries
    """
    base_url = f'https://api.jikan.moe/v4/seasons/{year}/{season}?filter=tv&continuing=true&filter=ona&sfw=true'
    all_shows = []
    current_page = 1
    has_next_page = True
    
    logger.info(f"Fetching {season} {year} anime...")
    
    while has_next_page:
        # Create URL with the current page parameter
        page_url = f"{base_url}&page={current_page}"
        
        logger.info(f"Fetching page {current_page}...")
        
        # Make request
        response = requests.get(page_url)
        
        # Check if request was successful
        if response.status_code == 200:
            data = response.json()
            
            # Get shows from current page
            shows = data.get('data', [])
            if shows:
                all_shows.extend(shows)
                logger.success(f"Retrieved {len(shows)} shows from page {current_page}")
            
            # Check pagination info
            pagination = data.get('pagination', {})
            has_next_page = pagination.get('has_next_page', False)
            current_page += 1
            
            # Wait to avoid rate limiting if there are more pages
            if has_next_page:
                logger.info(f"Waiting 10 seconds before fetching next page...")
                time.sleep(10)
        else:
            logger.error(f"Error: Received status code {response.status_code}")
            has_next_page = False
    
    logger.info(f"Total shows fetched: {len(all_shows)}")
    
    # Parse the data with Pydantic
    return MalSeasonals(mal_entries=all_shows)

def push_season_to_mongo(mal_entries: MalSeasonals, collection: Collection = None) -> None:
    """
    Pushes a list of MAL entries to a MongoDB collection.
    
    Args:
        mal_entries: List of MAL entries to push
        collection: MongoDB collection to push to
    """
    if not collection:
        client = MongoClient(os.getenv('MONGO_URI'))
        collection = client.anime.seasonal_entries
    for entry in mal_entries:
        try:
            entry_dict: Dict = entry.model_dump()
            collection.update_one({'mal_id': entry_dict['mal_id']}, {'$set': entry_dict}, upsert=True)
            logger.success(f"Pushed {entry_dict['title']} to MongoDB")
        except PydanticSchemaGenerationError as e:
            logger.error(f"Error generating the schema for {entry}: {e}")
            continue
        except PyMongoError as e:
            logger.error(f"Error pushing {entry} to MongoDB: {e}")
            continue
        except Exception as e:
            logger.error(f"Error pushing {entry} to MongoDB: {e}")
            continue
       