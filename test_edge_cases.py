from datetime import datetime, timezone
from util.seasonal_schedule import SeasonScheduler

# Test various dates around June 26, 2025 to see if there's any edge case
test_dates = [
    datetime(2025, 6, 26, 0, 0, 0, tzinfo=timezone.utc),  # June 26 midnight
    datetime(2025, 6, 26, 12, 0, 0, tzinfo=timezone.utc), # June 26 noon
    datetime(2025, 6, 26, 23, 59, 59, tzinfo=timezone.utc), # June 26 end of day
    datetime(2025, 6, 27, 0, 0, 0, tzinfo=timezone.utc), # June 27 midnight
    datetime(2025, 6, 27, 12, 0, 0, tzinfo=timezone.utc), # June 27 noon
]

print("=== Testing different times around June 26-27, 2025 ===")
for test_date in test_dates:
    print(f"\nTesting: {test_date}")
    
    # Test episodes schedule
    episodes_scheduler = SeasonScheduler(
        schedule_type='episodes',
        post_time=test_date
    )
    print(f"  Episodes: Season {episodes_scheduler.season_number} ({episodes_scheduler.season_name}), Week {episodes_scheduler.week_id}")
    
    # Test post schedule
    post_scheduler = SeasonScheduler(
        schedule_type='post',
        post_time=test_date
    )
    print(f"  Post: Season {post_scheduler.season_number} ({post_scheduler.season_name}), Week {post_scheduler.week_id}")

# Test with the default SeasonScheduler creation (like in post_processing.py)
print(f"\n=== Testing default SeasonScheduler creation ===")
default_scheduler = SeasonScheduler()
print(f"Default scheduler (current time): Season {default_scheduler.season_number} ({default_scheduler.season_name}), Week {default_scheduler.week_id}")

# Test with specific reference to post_processing.py usage
print(f"\n=== Testing SeasonScheduler(schedule_type='post') like in post_processing.py ===")
post_type_scheduler = SeasonScheduler(schedule_type='post')
print(f"Post type scheduler: Season {post_type_scheduler.season_number} ({post_type_scheduler.season_name}), Week {post_type_scheduler.week_id}")

# Also test the scenario from the user's description
print(f"\n=== Testing the specific scenario from user description ===")
# "posts da quinta feira dia 26" - Thursday June 26th
thursday_26 = datetime(2025, 6, 26, 14, 0, 0, tzinfo=timezone.utc)  # 2 PM on Thursday
scheduler_thursday = SeasonScheduler(schedule_type='post', post_time=thursday_26)
print(f"Thursday June 26, 2025 at 2 PM:")
print(f"  Season: {scheduler_thursday.season_number} ({scheduler_thursday.season_name})")
print(f"  Week: {scheduler_thursday.week_id}")
print(f"  Expected: Season 2 (spring), Week 13")
print(f"  Actual result matches expected: {scheduler_thursday.season_number == 2 and scheduler_thursday.week_id == 13}")
