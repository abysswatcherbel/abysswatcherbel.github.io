import unittest

from src.rank_processing import select_weekly_ranking_entries


class WeeklyRankingSelectionTests(unittest.TestCase):
    def test_excludes_episode_zero_and_limits_each_series_to_three(self):
        entries = [
            {
                "mal_id": 1,
                "episode": episode,
                "karma": karma,
                "comments": 0,
            }
            for episode, karma in [
                ("1", 500),
                ("10", 400),
                ("", 350),
                ("2", 300),
                ("3", 200),
            ]
        ]
        entries.append(
            {"mal_id": 2, "episode": "4", "karma": 250, "comments": 1}
        )

        selected = select_weekly_ranking_entries(entries)

        self.assertEqual(
            [(entry["mal_id"], entry["episode"]) for entry in selected],
            [(1, "1"), (1, "10"), (1, "2"), (2, "4")],
        )

    def test_uses_comments_as_the_karma_tiebreaker(self):
        entries = [
            {"mal_id": 1, "episode": "1", "karma": 100, "comments": 4},
            {"mal_id": 2, "episode": "1", "karma": 100, "comments": 8},
        ]

        selected = select_weekly_ranking_entries(entries)

        self.assertEqual([entry["mal_id"] for entry in selected], [2, 1])

    def test_rejects_invalid_limit(self):
        with self.assertRaises(ValueError):
            select_weekly_ranking_entries([], max_per_series=0)


if __name__ == "__main__":
    unittest.main()
