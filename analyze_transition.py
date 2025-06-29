import pandas as pd
from datetime import datetime, timezone

# Let's compare the transition dates between episodes and post schedules
print("=== COMPARING SPRING TO SUMMER TRANSITION ===")

# Episodes schedule
episodes_df = pd.read_csv('src/season_references/2025/episodes.csv')
episodes_df["start_date"] = pd.to_datetime(episodes_df["start_date"], utc=True)
episodes_df["end_date"] = pd.to_datetime(episodes_df["end_date"], utc=True)

print("Episodes Schedule - Spring Season 2 End:")
spring_end_episodes = episodes_df[(episodes_df['season'] == 2) & (episodes_df['week_id'] == 13)]
print(f"Week 13: {spring_end_episodes.iloc[0]['start_date']} to {spring_end_episodes.iloc[0]['end_date']}")

print("\nEpisodes Schedule - Summer Season 3 Start:")
summer_start_episodes = episodes_df[(episodes_df['season'] == 3) & (episodes_df['week_id'] == 1)]
print(f"Week 1: {summer_start_episodes.iloc[0]['start_date']} to {summer_start_episodes.iloc[0]['end_date']}")

# Post schedule
post_df = pd.read_csv('src/season_references/2025/post.csv')
post_df["start_date"] = pd.to_datetime(post_df["start_date"], utc=True)
post_df["end_date"] = pd.to_datetime(post_df["end_date"], utc=True)

print("\nPost Schedule - Spring Season 2 End:")
spring_end_post = post_df[(post_df['season'] == 2) & (post_df['week_id'] == 13)]
print(f"Week 13: {spring_end_post.iloc[0]['start_date']} to {spring_end_post.iloc[0]['end_date']}")

print("\nPost Schedule - Summer Season 3 Start:")
summer_start_post = post_df[(post_df['season'] == 3) & (post_df['week_id'] == 1)]
print(f"Week 1: {summer_start_post.iloc[0]['start_date']} to {summer_start_post.iloc[0]['end_date']}")

print("\n=== ANALYSIS ===")
print("Episodes schedule: Spring ends June 26, Summer starts June 27")
print("Post schedule: Spring ends June 29 12:59:59, Summer starts June 29 13:00:00")
print("\nThis means there's a 2-3 day difference between the schedules!")

# Test specific problematic dates
test_dates = [
    datetime(2025, 6, 26, 14, 0, 0, tzinfo=timezone.utc),  # Thursday June 26, 2 PM
    datetime(2025, 6, 27, 14, 0, 0, tzinfo=timezone.utc),  # Friday June 27, 2 PM
    datetime(2025, 6, 28, 14, 0, 0, tzinfo=timezone.utc),  # Saturday June 28, 2 PM
    datetime(2025, 6, 29, 12, 0, 0, tzinfo=timezone.utc),  # Sunday June 29, 12 PM
    datetime(2025, 6, 29, 14, 0, 0, tzinfo=timezone.utc),  # Sunday June 29, 2 PM
]

print("\n=== TESTING PROBLEMATIC DATES ===")
for test_date in test_dates:
    print(f"\n{test_date.strftime('%A %B %d, %Y at %I %p')}:")
    
    # Episodes schedule
    episodes_df_copy = episodes_df.copy()
    episodes_df_copy["end_date"] = episodes_df_copy["end_date"] + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
    
    episode_match = None
    for _, row in episodes_df_copy.iterrows():
        if row["start_date"] <= test_date <= row["end_date"]:
            episode_match = row
            break
    
    # Post schedule  
    post_match = None
    for _, row in post_df.iterrows():
        if row["start_date"] <= test_date <= row["end_date"]:
            post_match = row
            break
    
    if episode_match is not None:
        print(f"  Episodes: Season {episode_match['season']}, Week {episode_match['week_id']}")
    else:
        print(f"  Episodes: No match found")
        
    if post_match is not None:
        print(f"  Posts: Season {post_match['season']}, Week {post_match['week_id']}")
    else:
        print(f"  Posts: No match found")
        
    # Check if there's a mismatch
    if episode_match is not None and post_match is not None:
        if episode_match['season'] != post_match['season'] or episode_match['week_id'] != post_match['week_id']:
            print(f"  *** MISMATCH DETECTED ***")
