from pydantic import BaseModel, Field, field_validator
from typing import List, Dict, Optional, Any, Union
import time
import requests
from util.logger_config import logger

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
    
    @field_validator('year',mode='before')
    def set_year_from_aired(cls, v, values):
        if v is not None:
            return v
        
        try:
            aired = values.get('aired', {})
            prop = aired.get('prop', {})
            from_data = prop.get('from', {})
            return from_data.get('year')
        except (AttributeError, TypeError):
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