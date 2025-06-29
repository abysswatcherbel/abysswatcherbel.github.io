from datetime import datetime, timezone
from util.seasonal_schedule import SeasonScheduler

# Test the fix: June 26, 27, 28 should all be spring season 2, week 13 when using 'post' schedule
test_dates = [
    datetime(2025, 6, 26, 14, 0, 0, tzinfo=timezone.utc),  # Thursday June 26, 2 PM
    datetime(2025, 6, 27, 14, 0, 0, tzinfo=timezone.utc),  # Friday June 27, 2 PM  
    datetime(2025, 6, 28, 14, 0, 0, tzinfo=timezone.utc),  # Saturday June 28, 2 PM
]

print("=== TESTING THE FIX ===")
print("All dates should return Season 2 (spring), Week 13 when using 'post' schedule type")
print()

for test_date in test_dates:
    day_name = test_date.strftime('%A')
    print(f"{day_name} {test_date.strftime('%B %d, %Y at %I %p')}:")
    
    # Test the old behavior (episodes schedule - wrong for posts)
    episodes_scheduler = SeasonScheduler(schedule_type='episodes', post_time=test_date)
    print(f"  Episodes schedule (old behavior): Season {episodes_scheduler.season_number} ({episodes_scheduler.season_name}), Week {episodes_scheduler.week_id}")
    
    # Test the new behavior (post schedule - correct for posts)
    post_scheduler = SeasonScheduler(schedule_type='post', post_time=test_date)
    print(f"  Post schedule (new behavior):     Season {post_scheduler.season_number} ({post_scheduler.season_name}), Week {post_scheduler.week_id}")
    
    # Check if the fix resolves the issue
    if episodes_scheduler.season_number != post_scheduler.season_number or episodes_scheduler.week_id != post_scheduler.week_id:
        print(f"  ✓ FIX APPLIED: Different results between episodes and post schedules")
        if post_scheduler.season_number == 2 and post_scheduler.week_id == 13:
            print(f"  ✓ CORRECT: Post schedule correctly returns Season 2, Week 13")
        else:
            print(f"  ✗ ISSUE: Post schedule should return Season 2, Week 13")
    else:
        print(f"  → Same result for both schedules")
    print()

print("=== SUMMARY ===")    
print("The fix changes the post_processing.py functions to use schedule_type='post'")
print("instead of the default schedule_type='episodes' when processing Reddit posts.")
print("This ensures that posts created during the transition period (June 27-28)")
print("are correctly classified as Spring Season 2, Week 13 instead of Summer Season 3, Week 1.")
