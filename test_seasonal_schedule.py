from datetime import datetime, timezone
from util.seasonal_schedule import SeasonScheduler

# Test the issue: June 26, 2025 (Thursday) should be spring season 2, week 13
# but is returning summer season 3, week 12

# Create a SeasonScheduler for June 26, 2025
test_date = datetime(2025, 6, 26, 12, 0, 0, tzinfo=timezone.utc)
print(f"Testing date: {test_date}")

# Test with episodes schedule
episodes_scheduler = SeasonScheduler(
    schedule_type='episodes',
    post_time=test_date
)

print(f"\nEpisodes Schedule Results:")
print(f"Year: {episodes_scheduler.year}")
print(f"Month: {episodes_scheduler.month}")
print(f"Season Number: {episodes_scheduler.season_number}")
print(f"Season Name: {episodes_scheduler.season_name}")
print(f"Week ID: {episodes_scheduler.week_id}")
print(f"Schedule Details: {episodes_scheduler.schedule_detals}")

# Test with post schedule
post_scheduler = SeasonScheduler(
    schedule_type='post',
    post_time=test_date
)

print(f"\nPost Schedule Results:")
print(f"Year: {post_scheduler.year}")
print(f"Month: {post_scheduler.month}")
print(f"Season Number: {post_scheduler.season_number}")
print(f"Season Name: {post_scheduler.season_name}")
print(f"Week ID: {post_scheduler.week_id}")
print(f"Schedule Details: {post_scheduler.schedule_detals}")

# Let's also check what the CSV data looks like for the relevant dates
print("\n=== CSV Analysis ===")
import pandas as pd

# Check episodes.csv for spring season 2 (should be weeks 1-13)
episodes_df = pd.read_csv('src/season_references/2025/episodes.csv')
episodes_df["start_date"] = pd.to_datetime(episodes_df["start_date"], utc=True)
episodes_df["end_date"] = pd.to_datetime(episodes_df["end_date"], utc=True)

print("\nSpring 2025 episodes schedule (season 2):")
spring_episodes = episodes_df[episodes_df['season'] == 2]
print(spring_episodes[['week_id', 'start_date', 'end_date', 'season']])

print("\nSummer 2025 episodes schedule (season 3):")
summer_episodes = episodes_df[episodes_df['season'] == 3]
print(summer_episodes[['week_id', 'start_date', 'end_date', 'season']].head())

# Check post.csv for spring season 2
post_df = pd.read_csv('src/season_references/2025/post.csv')
post_df["start_date"] = pd.to_datetime(post_df["start_date"], utc=True)
post_df["end_date"] = pd.to_datetime(post_df["end_date"], utc=True)

print("\nSpring 2025 post schedule (season 2):")
spring_posts = post_df[post_df['season'] == 2]
print(spring_posts[['week_id', 'start_date', 'end_date', 'season']])

# Test the specific date manually
print(f"\n=== Manual Date Check ===")
print(f"Test date: {test_date}")

# Check if June 26, 2025 falls in spring season 2 week 13
spring_week_13 = spring_episodes[spring_episodes['week_id'] == 13].iloc[0]
print(f"Spring Season 2 Week 13: {spring_week_13['start_date']} to {spring_week_13['end_date']}")
print(f"Does test date fall in this range? {spring_week_13['start_date'] <= test_date <= spring_week_13['end_date']}")

# Check if it's incorrectly matching summer season 3
summer_week_1 = summer_episodes[summer_episodes['week_id'] == 1].iloc[0]
print(f"Summer Season 3 Week 1: {summer_week_1['start_date']} to {summer_week_1['end_date']}")
print(f"Does test date fall in this range? {summer_week_1['start_date'] <= test_date <= summer_week_1['end_date']}")
