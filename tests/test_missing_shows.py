import unittest
from datetime import datetime, timezone

from util.missing_shows import (
    audit_reddit_posts,
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


if __name__ == "__main__":
    unittest.main()
