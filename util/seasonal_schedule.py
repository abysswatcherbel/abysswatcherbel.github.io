from __future__ import annotations

import calendar
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Dict, Literal, Optional, Union
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field, field_validator, model_validator

from util.logger_config import logger


class ScheduleDetails(BaseModel):
    """Pydantic model for schedule details."""

    week_id: Optional[int] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    season: Optional[int] = None


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _last_weekday_of_month(year: int, month: int, weekday: int) -> date:
    """Return the last given weekday (0=Mon..6=Sun) in a month."""
    last_day = calendar.monthrange(year, month)[1]
    d = date(year, month, last_day)
    while d.weekday() != weekday:
        d -= timedelta(days=1)
    return d


def _episodes_season_start(schedule_year: int, season: int) -> datetime:
    """Season start for episode windows (Friday 00:00 UTC) for a season-year."""
    if season == 1:  # winter starts in Dec of previous calendar year
        y, m = schedule_year - 1, 12
    elif season == 2:
        y, m = schedule_year, 3
    elif season == 3:
        y, m = schedule_year, 6
    elif season == 4:
        y, m = schedule_year, 9
    else:
        raise ValueError(f"Invalid season: {season}")

    start_day = _last_weekday_of_month(y, m, calendar.FRIDAY)
    return datetime(
        start_day.year,
        start_day.month,
        start_day.day,
        0,
        0,
        0,
        tzinfo=timezone.utc,
    )


def _generate_episodes_schedule(schedule_year: int) -> list[dict]:
    rows: list[dict] = []
    for season in (1, 2, 3, 4):
        base = _episodes_season_start(schedule_year, season)
        for week_id in range(1, 14):
            start = base + timedelta(days=7 * (week_id - 1))
            end = start + timedelta(days=6, hours=23, minutes=59, seconds=59)
            rows.append(
                {
                    "schedule_year": schedule_year,
                    "schedule_type": "episodes",
                    "season": season,
                    "week_id": week_id,
                    "start_date": start,
                    "end_date": end,
                }
            )
    return rows


def _generate_post_schedule(schedule_year: int) -> list[dict]:
    """Generate DST-aware post windows.

    Posts happen Sunday 03:00 America/New_York (=> 07:00/08:00 UTC depending on DST).
    Each window covers exactly 7 days, ending at 06:59:59/07:59:59 UTC.
    """
    tz = ZoneInfo("America/New_York")
    rows: list[dict] = []
    for season in (1, 2, 3, 4):
        episode_start = _episodes_season_start(schedule_year, season)
        first_sunday = (episode_start + timedelta(days=2)).date()  # Fri -> Sun
        for week_id in range(1, 14):
            sunday = first_sunday + timedelta(days=7 * (week_id - 1))
            local_start = datetime.combine(sunday, time(3, 0), tzinfo=tz)
            start = local_start.astimezone(timezone.utc)
            end = start + timedelta(days=7) - timedelta(seconds=1)
            rows.append(
                {
                    "schedule_year": schedule_year,
                    "schedule_type": "post",
                    "season": season,
                    "week_id": week_id,
                    "start_date": start,
                    "end_date": end,
                }
            )
    return rows


@dataclass(frozen=True)
class _ScheduleRow:
    schedule_year: int
    schedule_type: str
    season: int
    week_id: int
    start_ts: int
    end_ts: int


class ScheduleCache:
    """SQLite-backed cache for schedules.

    Ensures schedules are generated once per (schedule_year, schedule_type)
    and then queried efficiently.
    """

    def __init__(self, db_path: Union[str, Path]):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schedules (
                    schedule_year INTEGER NOT NULL,
                    schedule_type TEXT NOT NULL,
                    season INTEGER NOT NULL,
                    week_id INTEGER NOT NULL,
                    start_ts INTEGER NOT NULL,
                    end_ts INTEGER NOT NULL,
                    start_iso TEXT NOT NULL,
                    end_iso TEXT NOT NULL,
                    PRIMARY KEY (schedule_year, schedule_type, season, week_id)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_sched_range ON schedules(schedule_year, schedule_type, start_ts, end_ts)"
            )

    def ensure_year(
        self, schedule_year: int, schedule_type: Literal["episodes", "post"]
    ) -> None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM schedules WHERE schedule_year=? AND schedule_type=?",
                (schedule_year, schedule_type),
            ).fetchone()
            if row and int(row["c"]) > 0:
                return

            logger.info(
                f"Building schedule cache for year={schedule_year} type={schedule_type}"
            )

            if schedule_type == "episodes":
                generated = _generate_episodes_schedule(schedule_year)
            else:
                generated = _generate_post_schedule(schedule_year)

            conn.executemany(
                """
                INSERT OR REPLACE INTO schedules
                    (schedule_year, schedule_type, season, week_id, start_ts, end_ts, start_iso, end_iso)
                VALUES
                    (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        r["schedule_year"],
                        r["schedule_type"],
                        r["season"],
                        r["week_id"],
                        int(_ensure_utc(r["start_date"]).timestamp()),
                        int(_ensure_utc(r["end_date"]).timestamp()),
                        _ensure_utc(r["start_date"]).isoformat(),
                        _ensure_utc(r["end_date"]).isoformat(),
                    )
                    for r in generated
                ],
            )

    def get_for_timestamp(
        self,
        schedule_year: int,
        schedule_type: Literal["episodes", "post"],
        ts: int,
    ) -> Optional[_ScheduleRow]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT schedule_year, schedule_type, season, week_id, start_ts, end_ts
                FROM schedules
                WHERE schedule_year=? AND schedule_type=? AND start_ts <= ? AND end_ts >= ?
                LIMIT 1
                """,
                (schedule_year, schedule_type, ts, ts),
            ).fetchone()
            if not row:
                return None
            return _ScheduleRow(
                schedule_year=int(row["schedule_year"]),
                schedule_type=str(row["schedule_type"]),
                season=int(row["season"]),
                week_id=int(row["week_id"]),
                start_ts=int(row["start_ts"]),
                end_ts=int(row["end_ts"]),
            )

    def get_for_week(
        self,
        schedule_year: int,
        schedule_type: Literal["episodes", "post"],
        season: int,
        week_id: int,
    ) -> Optional[_ScheduleRow]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT schedule_year, schedule_type, season, week_id, start_ts, end_ts
                FROM schedules
                WHERE schedule_year=? AND schedule_type=? AND season=? AND week_id=?
                LIMIT 1
                """,
                (schedule_year, schedule_type, season, week_id),
            ).fetchone()
            if not row:
                return None
            return _ScheduleRow(
                schedule_year=int(row["schedule_year"]),
                schedule_type=str(row["schedule_type"]),
                season=int(row["season"]),
                week_id=int(row["week_id"]),
                start_ts=int(row["start_ts"]),
                end_ts=int(row["end_ts"]),
            )


class SeasonScheduler(BaseModel):
    """Pydantic model for managing anime season schedules."""

    # Input parameters
    schedule_type: Literal["episodes", "post"] = Field(
        default="episodes", description="Type of schedule to use"
    )
    post_time: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Reference time for calculations",
    )
    cache_db_path: str = Field(
        default="database/schedules.sqlite",
        description="SQLite cache path for schedules",
    )

    # Derived fields (calculated from inputs)
    year: Optional[int] = Field(
        default=None, description="Year derived from post_time"
    )
    month: Optional[int] = Field(
        default=None, description="Month derived from post_time"
    )
    schedule_detals: Optional[ScheduleDetails] = Field(
        default=None, description="Details of the current schedule"
    )
    season_name: Optional[str] = Field(
        default=None, description="Season name derived from month"
    )
    season_number: Optional[int] = Field(
        default=None, description="Season number (1-4) derived from month"
    )
    week_id: Optional[int] = Field(
        default=None, description="Current week ID based on post_time"
    )
    airing_period: Optional[Dict[str, Union[str, int, None]]] = Field(
        default=None, description="Airing period details"
    )

    model_config = {
        "arbitrary_types_allowed": True,
        "populate_by_name": True,
    }

    # Validators
    @field_validator("post_time")
    def ensure_timezone_aware(cls, v):
        """Ensure post_time is timezone-aware (UTC)."""
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v

    @model_validator(mode="after")
    def calculate_derived_fields(self):
        """Calculate all derived fields based on post_time."""
        if self.post_time:
            utc_time = _ensure_utc(self.post_time)

            self.year = self._infer_schedule_year(utc_time)
            self.month = utc_time.month

            cache = ScheduleCache(self.cache_db_path)
            cache.ensure_year(self.year, self.schedule_type)

            ts = int(utc_time.timestamp())
            schedule_row = cache.get_for_timestamp(
                self.year, self.schedule_type, ts
            )
            if schedule_row is None:
                # Defensive fallback: try adjacent years.
                for candidate in (self.year - 1, self.year + 1):
                    cache.ensure_year(candidate, self.schedule_type)
                    schedule_row = cache.get_for_timestamp(
                        candidate, self.schedule_type, ts
                    )
                    if schedule_row is not None:
                        self.year = candidate
                        break

            if schedule_row is None:
                logger.error(
                    f"No schedule match for type={self.schedule_type} time={utc_time.isoformat()}"
                )
                self.schedule_detals = ScheduleDetails()
                self.season_number = None
                self.season_name = None
                self.week_id = None
                self.airing_period = None
                return self

            self.schedule_detals = ScheduleDetails(
                week_id=schedule_row.week_id,
                start_date=datetime.fromtimestamp(
                    schedule_row.start_ts, tz=timezone.utc
                ),
                end_date=datetime.fromtimestamp(
                    schedule_row.end_ts, tz=timezone.utc
                ),
                season=schedule_row.season,
            )

            self.season_number = self.schedule_detals.season
            self.season_name = self._get_season_name(self.season_number)
            self.week_id = self.schedule_detals.week_id
            self.airing_period = self.get_airing_period()

        return self

    @classmethod
    def _infer_schedule_year(cls, utc_time: datetime) -> int:
        """Infer the season-year for a timestamp.

        Winter season begins on the last Friday of December (00:00 UTC) and belongs
        to the *next* calendar year.
        """
        utc_time = _ensure_utc(utc_time)
        y = utc_time.year
        winter_next_start = _episodes_season_start(
            y + 1, 1
        )  # last Friday of Dec (year=y)
        if utc_time >= winter_next_start:
            return y + 1
        return y

    @classmethod
    def _get_season_name(cls, season_id: Optional[int]) -> str:
        """Get season name from month number."""
        if season_id is None:
            logger.error("Invalid season ID: None")
            raise ValueError("Invalid season ID: None")
        match season_id:
            case 1:
                return "winter"
            case 2:
                return "spring"
            case 3:
                return "summer"
            case 4:
                return "fall"
            case _:
                logger.error(f"Invalid season ID: {season_id}")
                raise ValueError(f"Invalid season ID: {season_id}")

    def get_schedule_for_date(
        self, year: int, season: int, week_id: int
    ) -> Optional[ScheduleDetails]:
        """Get schedule details for a specific date."""
        cache = ScheduleCache(self.cache_db_path)
        cache.ensure_year(year, self.schedule_type)
        logger.debug(
            f"Trying to find the schedule for year={year} season={season} week={week_id} type={self.schedule_type}"
        )
        row = cache.get_for_week(year, self.schedule_type, season, week_id)
        if row is None:
            return None
        return ScheduleDetails(
            week_id=row.week_id,
            start_date=datetime.fromtimestamp(row.start_ts, tz=timezone.utc),
            end_date=datetime.fromtimestamp(row.end_ts, tz=timezone.utc),
            season=row.season,
        )

    def check_and_create_schedule(self) -> bool:
        """Legacy hook kept for compatibility.

        Ensures the SQLite cache exists for the inferred year + schedule_type.
        Returns True if the cache had to be generated.
        """
        if self.year is None:
            return False
        cache = ScheduleCache(self.cache_db_path)
        with cache._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM schedules WHERE schedule_year=? AND schedule_type=?",
                (self.year, self.schedule_type),
            ).fetchone()
            already = row and int(row["c"]) > 0
        cache.ensure_year(self.year, self.schedule_type)
        return not bool(already)

    def get_week_id(self) -> Optional[int]:
        """Get the week ID for the current post_time."""
        return self.week_id

    def get_airing_period(
        self, schedule_details: Optional[ScheduleDetails] = None
    ) -> Dict[str, Union[str, int, None]]:
        """Get the airing period details for the current week."""
        if schedule_details is None:
            schedule_details = self.schedule_detals

        if (
            schedule_details is None
            or schedule_details.start_date is None
            or schedule_details.end_date is None
        ):
            return {
                "airing_period": None,
                "season": self.season_name,
                "week_id": self.week_id,
            }

        # Convert the dates to the desired format
        converted_start_date = schedule_details.start_date.strftime("%B, %d")
        converted_end_date = schedule_details.end_date.strftime("%B, %d")

        airing_period = (
            f"Airing Period: {converted_start_date} - {converted_end_date}"
        )

        return {
            "airing_period": airing_period,
            "season": self.season_name,
            "week_id": schedule_details.week_id,
        }
