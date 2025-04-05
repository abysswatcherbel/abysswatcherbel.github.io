from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Dict, Literal, Optional, Union, ClassVar
import os
from util.logger_config import logger

import pandas as pd
from pydantic import BaseModel, Field, field_validator, model_validator


class ScheduleDetails(BaseModel):
    """Pydantic model for schedule details."""

    week_id: int
    start_date: datetime
    end_date: datetime
    season: int

class SeasonScheduler(BaseModel):
    """Pydantic model for managing anime season schedules."""
    
    # Input parameters
    schedule_type: Literal['episodes', 'post'] = Field(default='episodes', description="Type of schedule to use")
    post_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Reference time for calculations")
    base_path: str = Field(default="src/season_references", description="Base path for schedule files")
    
    # Derived fields (calculated from inputs)
    year: Optional[int] = Field(default=None, description="Year derived from post_time")
    month: Optional[int] = Field(default=None, description="Month derived from post_time")
    schedule_csv: Optional[Path] = Field(default=None, description="Path to the schedule CSV file")
    schedule_detals: Optional[ScheduleDetails] = Field(default=None, description="Details of the current schedule")
    season_name: Optional[str] = Field(default=None, description="Season name derived from month")
    season_number: Optional[int] = Field(default=None, description="Season number (1-4) derived from month")
    week_id: Optional[int] = Field(default=None, description="Current week ID based on post_time")
    airing_period: Optional[Dict[str, Union[str, int, None]]] = Field(default=None, description="Airing period details")
    
    # Private cache variables (not serialized)
    _week_id_cache: Optional[int] = None
    
    model_config = {
        "arbitrary_types_allowed": True,
        "populate_by_name": True,
    }
    
    # Validators
    @field_validator('post_time')
    def ensure_timezone_aware(cls, v):
        """Ensure post_time is timezone-aware (UTC)."""
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v
    
    @model_validator(mode='after')
    def calculate_derived_fields(self):
        """Calculate all derived fields based on post_time."""
        if self.post_time:
            self.year = self.post_time.year
            self.month = self.post_time.month
            self.schedule_csv = self.get_schedule_path()
            self.schedule_detals = self._get_schedule_details(self.schedule_type, self.schedule_csv, self.post_time)
            self.season_number = self.schedule_detals.season
            self.season_name = self._get_season_name(self.season_number)
            self.week_id = self.schedule_detals.week_id
            self.airing_period = self.get_airing_period()
            
        return self
    
    # Class methods (static helpers)
    @classmethod
    def _get_schedule_details(cls, schedule_type: str ,schedule_csv: Path, current_time: datetime) -> ScheduleDetails:
        """Get schedule details for the current time."""
        logger.info(f'Getting schedule details for {schedule_type} at {current_time} on {schedule_csv}')
        schedule_df = pd.read_csv(schedule_csv)
        schedule_df["start_date"] = pd.to_datetime(schedule_df["start_date"], utc=True)
        schedule_df["end_date"] = pd.to_datetime(schedule_df["end_date"], utc=True)
        
        # Process dates based on schedule type
        if schedule_type == 'episodes':
            # Adjust end_date to cover the entire day
            schedule_df["end_date"] = (
                schedule_df["end_date"] + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
            )
        
        # Ensure post_time is timezone-aware
        post_time = current_time
        if post_time.tzinfo is None:
            post_time = post_time.replace(tzinfo=timezone.utc)
        
        # Find the matching week
        for _, row in schedule_df.iterrows():
            if row["start_date"] <= post_time <= row["end_date"]:
                return ScheduleDetails(
                    week_id=int(row["week_id"]),
                    start_date=row["start_date"],
                    end_date=row["end_date"],
                    season=int(row['season'])
                )
        
        return ScheduleDetails(week_id=None, start_date=None, end_date=None, season=None)
    @classmethod
    def _get_season_name(cls, season_id: int) -> str:
        """Get season name from month number."""
        match season_id:
            case 1:
                return 'winter'
            case 2:
                return 'spring'
            case 3:
                return 'summer'
            case 4:
                return 'fall'
            case _:
                logger.error(f"Invalid season ID: {season_id}")
                raise ValueError(f"Invalid season ID: {season_id}")
    
    def get_schedule_for_date(self, year: int ,season: int, week_id: int) -> Optional[ScheduleDetails]:
        """Get schedule details for a specific date."""
        # Construct the path to the schedule CSV file
        schedule_path = Path(self.base_path) / str(year) / f"{self.schedule_type}.csv"
        
        if not schedule_path.exists():
            logger.error(f"Schedule file does not exist: {schedule_path}")
            return None
        
         # Process dates based on schedule type
        
        
        # Load the schedule CSV file
        schedule_df = pd.read_csv(schedule_path)

        logger.debug(f'Trying to find the schedule for {year} {season} week {week_id} with the path {schedule_path}')
        
        # Convert start_date and end_date to datetime objects
        schedule_df["start_date"] = pd.to_datetime(schedule_df["start_date"], utc=True)
        schedule_df["end_date"] = pd.to_datetime(schedule_df["end_date"], utc=True)

         # Process dates based on schedule type
        if self.schedule_type == 'episodes':
            # Adjust end_date to cover the entire day
            schedule_df["end_date"] = (
                schedule_df["end_date"] + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
            )
        
        # Find the matching week
        for _, row in schedule_df.iterrows():
            if row["week_id"] == week_id and row["season"] == season:
                return ScheduleDetails(
                    week_id=int(row["week_id"]),
                    start_date=row["start_date"],
                    end_date=row["end_date"],
                    season=int(row['season'])
                )
        
        return None
      
    
    # Instance methods
    def get_schedule_path(self) -> Path:
        """Get the path to the schedule CSV file."""
        return Path(self.base_path) / str(self.year) / f"{self.schedule_type}.csv"
    
    def check_and_create_schedule(self) -> bool:
        """Check if schedule exists and create it if it doesn't. Returns True if created."""
        schedule_path = self.get_schedule_path()
        
        if schedule_path.exists():
            return False
        
        # Ensure directory exists
        schedule_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create a default schedule based on the season and schedule type
        if self.schedule_type == 'post':
            self._create_post_schedule(schedule_path)
        else:
            self._create_episodes_schedule(schedule_path)
        
        return True
    
    def _create_post_schedule(self, schedule_path: Path) -> None:
        """Create a default post schedule CSV file."""
        # For post schedule, determine appropriate start date based on season
        if self.season_name == 'spring':
            start_date = datetime(self.year, 3, 30, 13, 0, 0, tzinfo=timezone.utc)
        elif self.season_name == 'summer':
            start_date = datetime(self.year, 6, 29, 13, 0, 0, tzinfo=timezone.utc)
        elif self.season_name == 'fall':
            start_date = datetime(self.year, 9, 28, 13, 0, 0, tzinfo=timezone.utc)
        else:  # Winter
            start_date = datetime(self.year, 12, 28, 13, 0, 0, tzinfo=timezone.utc)
        
        weeks = []
        for week_id in range(1, 14):  # 13 weeks per season
            end_date = start_date + pd.Timedelta(days=7) - pd.Timedelta(seconds=1)
            weeks.append({
                "week_id": week_id,
                "start_date": start_date.strftime("%Y-%m-%d %H:%M:%S+00:00"),
                "end_date": end_date.strftime("%Y-%m-%d %H:%M:%S+00:00")
            })
            start_date = end_date + pd.Timedelta(seconds=1)
        
        pd.DataFrame(weeks).to_csv(schedule_path, index=False)
    
    def _create_episodes_schedule(self, schedule_path: Path) -> None:
        """Create a default episodes schedule CSV file."""
        # For episodes schedule, determine appropriate start date based on season
        logger.warning(f"Creating {self.schedule_type} schedule for {self.season_name} {self.year}")
        if self.season_name == 'spring':
            start_date = datetime(self.year, 3, 28, tzinfo=timezone.utc)
        elif self.season_name == 'summer':
            start_date = datetime(self.year, 6, 27, tzinfo=timezone.utc)
        elif self.season_name == 'fall':
            start_date = datetime(self.year, 9, 26, tzinfo=timezone.utc)
        else:  # Winter
            start_date = datetime(self.year, 12, 26, tzinfo=timezone.utc)
        
        weeks = []
        for week_id in range(1, 14):  # 13 weeks per season
            end_date = start_date + pd.Timedelta(days=6)
            weeks.append({
                "week_id": week_id,
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d")
            })
            start_date = end_date + pd.Timedelta(days=1)
        
        pd.DataFrame(weeks).to_csv(schedule_path, index=False)
    
   
    
    def get_week_id(self) -> Optional[int]:
        """Get the week ID for the current post_time."""
        return self.week_id
    
    def get_airing_period(self) -> Dict[str, Union[str, int, None]]:
        """Get the airing period details for the current week."""
        
        # Convert the dates to the desired format
        converted_start_date = self.schedule_detals.start_date.strftime("%B, %d")
        converted_end_date = self.schedule_detals.end_date.strftime("%B, %d")
        
        airing_period = f"Airing Period: {converted_start_date} - {converted_end_date}"
        
        return {
            "airing_period": airing_period,
            "season": self.season_name,
            "week_id": self.week_id,
        }


