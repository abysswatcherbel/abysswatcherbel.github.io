from datetime import datetime, timezone
import pandas as pd

# Let's debug the issue more carefully
test_date = datetime(2025, 6, 26, 12, 0, 0, tzinfo=timezone.utc)
print(f"Testing date: {test_date}")

# Load the episodes CSV and check the date processing
episodes_df = pd.read_csv('src/season_references/2025/episodes.csv')
print(f"\nOriginal CSV data for spring season 2, week 13:")
spring_week_13_raw = episodes_df[(episodes_df['season'] == 2) & (episodes_df['week_id'] == 13)]
print(spring_week_13_raw)

# Convert dates like the SeasonScheduler does
episodes_df["start_date"] = pd.to_datetime(episodes_df["start_date"], utc=True)
episodes_df["end_date"] = pd.to_datetime(episodes_df["end_date"], utc=True)

# Apply the episodes schedule logic (extend end_date)
episodes_df["end_date"] = (
    episodes_df["end_date"] + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
)

print(f"\nAfter processing (like SeasonScheduler does):")
spring_week_13_processed = episodes_df[(episodes_df['season'] == 2) & (episodes_df['week_id'] == 13)]
print(spring_week_13_processed[['week_id', 'start_date', 'end_date', 'season']])

# Check if test date falls in the processed range
start_date = spring_week_13_processed.iloc[0]['start_date']
end_date = spring_week_13_processed.iloc[0]['end_date']
print(f"\nProcessed range: {start_date} to {end_date}")
print(f"Test date {test_date} falls in range? {start_date <= test_date <= end_date}")

# Let's also check what happens if we don't get the right match
print(f"\n=== Debugging the actual SeasonScheduler logic ===")

# Simulate the exact logic from _get_schedule_details
schedule_df = pd.read_csv('src/season_references/2025/episodes.csv')
schedule_df["start_date"] = pd.to_datetime(schedule_df["start_date"], utc=True)
schedule_df["end_date"] = pd.to_datetime(schedule_df["end_date"], utc=True)

# Process dates based on schedule type (episodes)
schedule_df["end_date"] = (
    schedule_df["end_date"] + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
)

print(f"Looking for matches for {test_date}:")
for _, row in schedule_df.iterrows():
    if row["start_date"] <= test_date <= row["end_date"]:
        print(f"MATCH: Week {row['week_id']}, Season {row['season']}")
        print(f"  Range: {row['start_date']} to {row['end_date']}")
        break
else:
    print("No match found!")

# Let's check a few specific ranges around the date
print(f"\n=== Checking ranges around June 26, 2025 ===")
relevant_rows = schedule_df[
    (schedule_df['start_date'] <= test_date + pd.Timedelta(days=2)) &
    (schedule_df['end_date'] >= test_date - pd.Timedelta(days=2))
]
for _, row in relevant_rows.iterrows():
    in_range = row["start_date"] <= test_date <= row["end_date"]
    print(f"Week {row['week_id']}, Season {row['season']}: {row['start_date']} to {row['end_date']} - Match: {in_range}")
