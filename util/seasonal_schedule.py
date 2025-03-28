from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Dict, Literal, Optional, Union, ClassVar
import os
from util.logger_config import logger

import pandas as pd
from pydantic import BaseModel, Field, field_validator, model_validator


class Season(str, Enum):
    WINTER = "winter"
    SPRING = "spring"
    SUMMER = "summer"
    FALL = "fall"


class ScheduleType(str, Enum):
    EPISODES = "episodes"
    POST = "post"


class SeasonScheduler(BaseModel):
    """Pydantic model for managing anime season schedules."""
    
    # Input parameters
    schedule_type: ScheduleType = Field(default=ScheduleType.EPISODES, description="Type of schedule to use")
    post_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Reference time for calculations")
    base_path: str = Field(default="src/season_references", description="Base path for schedule files")
    
    # Derived fields (calculated from inputs)
    year: Optional[int] = Field(default=None, description="Year derived from post_time")
    month: Optional[int] = Field(default=None, description="Month derived from post_time")
    season_name: Optional[Season] = Field(default=None, description="Season name derived from month")
    season_number: Optional[int] = Field(default=None, description="Season number (1-4) derived from month")
    week_id: Optional[int] = Field(default=None, description="Current week ID based on post_time")
    
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
            self.season_name = self._get_season_name(self.month)
            self.season_number = self._get_season_number(self.month)
            self.week_id = self.get_week_id()
        return self
    
    # Class methods (static helpers)
    @classmethod
    def _get_season_name(cls, month_int: int) -> Season:
        """Get season name from month number."""
        if month_int in range(1, 4):
            return Season.WINTER
        elif month_int in range(4, 7):
            return Season.SPRING
        elif month_int in range(7, 10):
            return Season.SUMMER
        elif month_int in range(10, 13):
            return Season.FALL
        else:
            raise ValueError("Invalid month integer. Please provide a value between 1 and 12.")
    
    @classmethod
    def _get_season_number(cls, month_int: int) -> int:
        """Get season number (1-4) from month number."""
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
    
    # Instance methods
    def get_schedule_path(self) -> Path:
        """Get the path to the schedule CSV file."""
        return Path(self.base_path) / str(self.year) / self.season_name.value / f"{self.schedule_type.value}.csv"
    
    def check_and_create_schedule(self) -> bool:
        """Check if schedule exists and create it if it doesn't. Returns True if created."""
        schedule_path = self.get_schedule_path()
        
        if schedule_path.exists():
            return False
        
        # Ensure directory exists
        schedule_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create a default schedule based on the season and schedule type
        if self.schedule_type == ScheduleType.POST:
            self._create_post_schedule(schedule_path)
        else:
            self._create_episodes_schedule(schedule_path)
        
        return True
    
    def _create_post_schedule(self, schedule_path: Path) -> None:
        """Create a default post schedule CSV file."""
        # For post schedule, determine appropriate start date based on season
        if self.season_name == Season.SPRING:
            start_date = datetime(self.year, 3, 30, 13, 0, 0, tzinfo=timezone.utc)
        elif self.season_name == Season.SUMMER:
            start_date = datetime(self.year, 6, 29, 13, 0, 0, tzinfo=timezone.utc)
        elif self.season_name == Season.FALL:
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
        if self.season_name == Season.SPRING:
            start_date = datetime(self.year, 3, 28, tzinfo=timezone.utc)
        elif self.season_name == Season.SUMMER:
            start_date = datetime(self.year, 6, 27, tzinfo=timezone.utc)
        elif self.season_name == Season.FALL:
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
    
    def load_schedule_df(self) -> pd.DataFrame:
        """Load the schedule DataFrame, creating it if necessary."""
        # Check and create schedule if it doesn't exist
        self.check_and_create_schedule()
        
        # Load the schedule file
        schedule_path = self.get_schedule_path()
        schedule_df = pd.read_csv(schedule_path)
        
        # Process dates based on schedule type
        if self.schedule_type == ScheduleType.POST:
            # Convert to timezone-aware datetimes (UTC)
            schedule_df["start_date"] = pd.to_datetime(schedule_df["start_date"], utc=True)
            schedule_df["end_date"] = pd.to_datetime(schedule_df["end_date"], utc=True)
        else:
            # Convert to dates and then to timezone-aware datetimes
            schedule_df["start_date"] = pd.to_datetime(schedule_df["start_date"], utc=True)
            schedule_df["end_date"] = pd.to_datetime(schedule_df["end_date"], utc=True)
            # Adjust end_date to cover the entire day
            schedule_df["end_date"] = (
                schedule_df["end_date"] + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
            )
        
        return schedule_df
    
    def get_week_id(self) -> Optional[int]:
        """Get the week ID for the current post_time."""
        if self._week_id_cache is None:
            schedule_df = self.load_schedule_df()
            
            # Ensure post_time is timezone-aware
            post_time = self.post_time
            if post_time.tzinfo is None:
                post_time = post_time.replace(tzinfo=timezone.utc)
            
            # Find the matching week
            for _, row in schedule_df.iterrows():
                if row["start_date"] <= post_time <= row["end_date"]:
                    self._week_id_cache = int(row["week_id"])
                    break
            else:
                self._week_id_cache = None
            
            # Update the instance field
            self.week_id = self._week_id_cache
            
        return self._week_id_cache
    
    def get_airing_period(self) -> Dict[str, Union[str, int, None]]:
        """Get the airing period details for the current week."""
        # Ensure week_id is calculated
        week_id = self.get_week_id()
        
        if week_id is None:
            return {
                "airing_period": "No current airing period found",
                "season": self.season_name.value,
                "week_id": None
            }
        
        schedule_df = self.load_schedule_df()
        
        # Filter the DataFrame by week_id
        week_row = schedule_df[schedule_df["week_id"] == week_id]
        
        if week_row.empty:
            return {
                "airing_period": f"No schedule found for week_id: {week_id}",
                "season": self.season_name.value,
                "week_id": week_id
            }
        
        # Get start_date and end_date from the filtered row
        start_date = week_row["start_date"].iloc[0]
        end_date = week_row["end_date"].iloc[0]
        
        # Convert the dates to the desired format
        converted_start_date = start_date.strftime("%B, %d")
        converted_end_date = end_date.strftime("%B, %d")
        
        airing_period = f"Airing Period: {converted_start_date} - {converted_end_date}"
        
        return {
            "airing_period": airing_period,
            "season": self.season_name.value,
            "week_id": week_id,
        }


# Example usage:
if __name__ == "__main__":
    # Create a scheduler for the current time
    scheduler = SeasonScheduler()
    
    # Get the current week ID
    current_week_id = scheduler.get_week_id()
    print(f"Current Week ID: {current_week_id}")
    
    # Get airing period details
    airing_details = scheduler.get_airing_period()
    print(f"Airing Period: {airing_details['airing_period']}")
    print(f"Season: {airing_details['season']}")
    
    # Create a scheduler for posts
    post_scheduler = SeasonScheduler(schedule_type=ScheduleType.POST)
    post_airing_details = post_scheduler.get_airing_period()
    print(f"Post Airing Period: {post_airing_details['airing_period']}")