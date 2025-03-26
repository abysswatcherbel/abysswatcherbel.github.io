from pydantic import BaseModel, Field, field_validator, ValidationError, PydanticSchemaGenerationError, PydanticUserError
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

class MalImageSet(BaseModel):
    image_url: Optional[str] = None
    small_image_url: Optional[str] = None
    large_image_url: Optional[str] = None

class MalImages(BaseModel):
    jpg: MalImageSet
    webp: MalImageSet

class MalDateProp(BaseModel):
    day: Optional[int] = None
    month: Optional[int] = None
    year: Optional[int] = None

class MalAiringProps(BaseModel):
    from_: MalDateProp = Field(..., alias="from")
    to: Optional[MalDateProp] = None

class MalAiringDetails(BaseModel):
    from_: Optional[str] = Field(None, alias="from")
    to: Optional[str] = None
    prop: MalAiringProps
    string: str

class MalEntity(BaseModel):
    mal_id: int
    type: str
    name: str
    url: str

class MalEntry(BaseModel):
    mal_id: int
    url: str
    images: MalImages
    title: str
    title_english: Optional[str] = None
    type: str
    source: str
    episodes: Optional[int] = None
    status: str
    airing: bool
    aired: MalAiringDetails
    score: Optional[float] = None
    season: Optional[str] = None
    year: Optional[int] = None
    producers: List[MalEntity] = []
    licensors: List[MalEntity] = []
    studios: List[MalEntity] = []
    genres: List[MalEntity] = []

    @field_validator( "year", mode='plain' )
    @classmethod
    def set_year_from_aired(cls, year, airing_details: MalAiringDetails) -> Optional[int]:
        if year:
            return year
        
        try:
            # Get the data object that contains all values
            data = airing_details.model_dump()
            
            # Log what we're working with for debugging
            logger.debug(f"Setting year from aired in validator, data: {data.get('aired')}")
            
            # Access the aired data
            aired = data.get('aired')
            if not aired:
                return None
                
            # Access the prop data - we need to use from_ because of the alias
            prop = aired.get('prop')
            if not prop:
                return None
                
            # Access the from data - again using from_ because of the alias
            from_data = prop.get('from_')
            if not from_data:
                return None
                
            # Finally get the year
            year = from_data.get('year')
            logger.success(f"Found year: {year}")
            return year
            
        except PydanticUserError as e:
            logger.error(f"Error in the setup of the validation for year: {e}")
            return None
    
   

class MalSeasonals(BaseModel):
    mal_entries: List[MalEntry]



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
        finally:
            client.close()
            logger.success(f"Pushed {len(mal_entries)} entries to MongoDB")