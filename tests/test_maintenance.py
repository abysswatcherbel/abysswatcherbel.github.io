import unittest

from util.maintenance import (
    extract_mal_id,
    normalize_anilist_links,
    normalize_stream_offers,
    season_scope,
    validate_season,
)


class MaintenanceTests(unittest.TestCase):
    def test_extracts_mal_id(self):
        self.assertEqual(
            extract_mal_id("https://myanimelist.net/anime/61990/Cyberpunk"),
            61990,
        )

    def test_normalizes_legal_streams_and_ignores_nyaa(self):
        offers = normalize_stream_offers(
            {
                "hidive|HIDIVE": "hidive.com/example",
                "crunchyroll|Crunchyroll": "https://crunchyroll.com/example",
                "nyaa": "https://example.invalid/torrent",
            }
        )
        self.assertEqual(
            [offer["provider"] for offer in offers],
            ["crunchyroll", "hidive"],
        )
        self.assertEqual(offers[1]["url"], "https://hidive.com/example")

    def test_season_scope_supports_metadata_and_karma_paths(self):
        self.assertEqual(
            season_scope(2026, "fall"),
            {
                "$or": [
                    {"year": 2026, "season": "fall"},
                    {"reddit_karma.2026.fall": {"$exists": True}},
                ]
            },
        )

    def test_normalizes_anilist_streaming_links_only(self):
        offers = normalize_anilist_links(
            [
                {
                    "site": "Amazon Prime Video",
                    "url": "https://amazon.example/show",
                    "type": "STREAMING",
                    "isDisabled": False,
                },
                {
                    "site": "Official Site",
                    "url": "https://example.com",
                    "type": "INFO",
                    "isDisabled": False,
                },
            ]
        )
        self.assertEqual(offers[0]["provider"], "amazon")

    def test_rejects_unknown_season(self):
        with self.assertRaises(ValueError):
            validate_season(2026, "monsoon")


if __name__ == "__main__":
    unittest.main()
