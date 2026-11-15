import unittest
from datetime import datetime, timezone

from util.missing_shows import (
    audit_reddit_posts,
    build_episode_record,
    estimate_hour_48_karma,
    extract_episode,
    extract_reddit_post_id,
    is_rankable_episode,
)


class MissingShowsTests(unittest.TestCase):
    def test_extracts_post_id_from_url(self):
        self.assertEqual(
            extract_reddit_post_id(
                "https://www.reddit.com/r/anime/comments/1xdgi4o/title/"
            ),
            "1xdgi4o",
        )

    def test_episode_zero_is_not_rankable(self):
        self.assertFalse(is_rankable_episode("Example - Episode 0 discussion"))
        self.assertTrue(is_rankable_episode("Example - Episode 3 discussion"))
        self.assertEqual(extract_episode("Example - Episode 3 discussion"), "3")

    def test_finds_tracked_post_missing_after_48_hours(self):
        now = datetime(2026, 10, 31, tzinfo=timezone.utc)
        posts = [
            {
                "reddit_id": "1xdgi4o",
                "created_utc": datetime(2026, 10, 23, tzinfo=timezone.utc).timestamp(),
            }
        ]
        results = audit_reddit_posts(
            posts,
            finalized_ids=set(),
            watch_entries={
                "1xdgi4o": {"hourly_karma": [{"hour": 48.0, "karma": 374}]}
            },
            now=now,
        )
        self.assertEqual(results[0]["status"], "missing_finalization")
        self.assertEqual(results[0]["expected_karma"], 374)

    def test_finalized_post_is_not_missing(self):
        now = datetime(2026, 10, 31, tzinfo=timezone.utc)
        results = audit_reddit_posts(
            [
                {
                    "reddit_id": "abc123",
                    "created_utc": datetime(
                        2026, 10, 20, tzinfo=timezone.utc
                    ).timestamp(),
                }
            ],
            finalized_ids={"abc123"},
            watch_entries={},
            now=now,
        )
        self.assertEqual(results[0]["status"], "finalized")

    def test_builds_repair_record_from_hour_48_snapshot(self):
        record = build_episode_record(
            {
                "week_id": 7,
                "episode": "6",
                "expected_karma": 132,
                "expected_karma_hour": 48.0,
                "comments": 42,
                "upvote_ratio": 0.96,
                "reddit_id": "1xtnl57",
                "url": "https://www.reddit.com/r/anime/comments/1xtnl57/example/",
            }
        )
        self.assertEqual(record["karma"], 132)
        self.assertEqual(record["week_id"], 7)

    def test_rejects_repair_without_hour_48_snapshot(self):
        with self.assertRaisesRegex(ValueError, "hour-48"):
            build_episode_record(
                {
                    "week_id": 7,
                    "episode": "6",
                    "expected_karma": 120,
                    "expected_karma_hour": 47.0,
                    "comments": 42,
                    "upvote_ratio": 0.96,
                    "reddit_id": "abc123",
                    "url": "https://www.reddit.com/r/anime/comments/abc123/example/",
                }
            )

    def test_force_uses_latest_snapshot_and_marks_estimate(self):
        record = build_episode_record(
            {
                "week_id": 7,
                "episode": "6",
                "expected_karma": 132,
                "expected_karma_hour": 47.0,
                "comments": 42,
                "upvote_ratio": 0.96,
                "reddit_id": "1xtnl57",
                "url": "https://www.reddit.com/r/anime/comments/1xtnl57/example/",
            },
            force=True,
        )
        self.assertEqual(record["karma"], 132)
        self.assertTrue(record["karma_estimated"])
        self.assertEqual(record["karma_snapshot_hour"], 47.0)
        self.assertEqual(record["karma_source"], "latest_hourly_snapshot")

    def test_force_falls_back_to_current_reddit_karma(self):
        record = build_episode_record(
            {
                "week_id": 7,
                "episode": "6",
                "expected_karma": None,
                "expected_karma_hour": None,
                "current_karma": 140,
                "comments": 42,
                "upvote_ratio": 0.96,
                "reddit_id": "abc123",
                "url": "https://www.reddit.com/r/anime/comments/abc123/example/",
            },
            force=True,
        )
        self.assertEqual(record["karma"], 140)
        self.assertEqual(record["karma_source"], "reddit_current")

    def test_estimates_hour_48_from_historical_median(self):
        estimate, multiplier, sample_size = estimate_hour_48_karma(
            snapshot_karma=100,
            growth_ratios=[1.1, 1.2, 1.3],
            current_karma=140,
        )
        self.assertEqual(estimate, 120)
        self.assertEqual(multiplier, 1.2)
        self.assertEqual(sample_size, 3)

    def test_estimate_is_capped_by_current_reddit_score(self):
        estimate, _, _ = estimate_hour_48_karma(
            snapshot_karma=100,
            growth_ratios=[2.0],
            current_karma=130,
        )
        self.assertEqual(estimate, 130)

    def test_force_record_keeps_estimation_provenance(self):
        record = build_episode_record(
            {
                "week_id": 7,
                "episode": "6",
                "expected_karma": 132,
                "expected_karma_hour": 21.0,
                "estimated_48h_karma": 150,
                "karma_estimation_multiplier": 1.1386,
                "karma_estimation_sample_size": 272,
                "comments": 42,
                "upvote_ratio": 0.96,
                "reddit_id": "1xtnl57",
                "url": "https://www.reddit.com/r/anime/comments/1xtnl57/example/",
            },
            force=True,
        )
        self.assertEqual(record["karma"], 150)
        self.assertEqual(record["karma_source"], "historical_median_curve")
        self.assertEqual(record["karma_estimation_sample_size"], 272)


if __name__ == "__main__":
    unittest.main()
