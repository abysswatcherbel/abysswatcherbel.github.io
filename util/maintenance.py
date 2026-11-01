from __future__ import annotations

import re
import time
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

import requests
import yaml
from pymongo import MongoClient


VALID_SEASONS = {"winter", "spring", "summer", "fall"}
MAL_URL_PATTERN = re.compile(
    r"https?://(?:www\.)?myanimelist\.net/anime/(\d+)", re.IGNORECASE
)
DEFAULT_HOLO_URL = (
    "https://raw.githubusercontent.com/r-anime/holo/master/"
    "season_configs/{season}_{year}.yaml"
)
ANILIST_API_URL = "https://graphql.anilist.co"
PROVIDER_ORDER = (
    "crunchyroll",
    "hidive",
    "netflix",
    "disney",
    "hulu",
    "youtube",
    "amazon",
    "museasia",
    "anione",
)


def validate_season(year: int, season: str) -> tuple[int, str]:
    normalized = season.strip().lower()
    if normalized not in VALID_SEASONS:
        raise ValueError(f"season must be one of: {', '.join(sorted(VALID_SEASONS))}")
    if year < 2000:
        raise ValueError("year must be 2000 or later")
    return year, normalized


def season_scope(year: int, season: str) -> dict[str, Any]:
    year, season = validate_season(year, season)
    return {
        "$or": [
            {"year": year, "season": season},
            {f"reddit_karma.{year}.{season}": {"$exists": True}},
        ]
    }


def extract_mal_id(value: Any) -> int | None:
    match = MAL_URL_PATTERN.search(str(value or ""))
    return int(match.group(1)) if match else None


def normalize_stream_offers(raw_streams: Any) -> list[dict[str, str]]:
    """Convert Holo's stream mapping to ordered, legal provider offers."""
    if not isinstance(raw_streams, dict):
        return []

    offers: list[dict[str, str]] = []
    for raw_name, raw_url in raw_streams.items():
        if not isinstance(raw_url, str) or not raw_url.strip():
            continue
        provider, _, display_name = str(raw_name).partition("|")
        provider = provider.strip().lower()
        if provider == "nyaa":
            continue
        url = raw_url.strip()
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"
        offers.append(
            {
                "provider": provider,
                "name": display_name.strip() or provider,
                "url": url,
            }
        )

    preferred = {name: index for index, name in enumerate(PROVIDER_ORDER)}
    return sorted(offers, key=lambda item: preferred.get(item["provider"], 99))


def provider_slug(site: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "", site.lower())
    aliases = {
        "amazonprimevideo": "amazon",
        "disneyplus": "disney",
        "youtube": "youtube",
    }
    return aliases.get(normalized, normalized)


def normalize_anilist_links(raw_links: Any) -> list[dict[str, str]]:
    if not isinstance(raw_links, list):
        return []
    offers = []
    for link in raw_links:
        if not isinstance(link, dict):
            continue
        if link.get("type") != "STREAMING" or link.get("isDisabled"):
            continue
        site = str(link.get("site") or "").strip()
        url = str(link.get("url") or "").strip()
        if not site or not url:
            continue
        offers.append(
            {"provider": provider_slug(site), "name": site, "url": url}
        )
    preferred = {name: index for index, name in enumerate(PROVIDER_ORDER)}
    return sorted(offers, key=lambda item: preferred.get(item["provider"], 99))


class MalApiClient:
    ENTRY_URL = "https://api.myanimelist.net/v2/anime"

    def __init__(self, client_id: str):
        if not client_id:
            raise RuntimeError("MAL_SECRET must be set")
        self.session = requests.Session()
        self.session.headers.update({"X-MAL-CLIENT-ID": client_id})

    def fetch_score(
        self,
        mal_id: int,
        *,
        progress: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        fields = ",".join(
            (
                "id",
                "mean",
                "rank",
                "popularity",
                "num_list_users",
                "num_scoring_users",
                "statistics",
            )
        )
        for attempt in range(3):
            response = self.session.get(
                f"{self.ENTRY_URL}/{mal_id}",
                params={"fields": fields},
                timeout=30,
            )
            if response.status_code != 429:
                response.raise_for_status()
                return response.json()
            if attempt < 2:
                retry_after = min(int(response.headers.get("Retry-After", "10")), 60)
                if progress is not None:
                    progress(
                        f"MAL rate limit reached for {mal_id}; "
                        f"retrying in {retry_after}s (attempt {attempt + 2}/3)"
                    )
                time.sleep(retry_after)
        response.raise_for_status()
        raise AssertionError("unreachable")


def update_mal_scores(
    *,
    mongo_uri: str,
    mal_client_id: str,
    year: int,
    season: str,
    week: int | None = None,
    missing_only: bool = False,
    dry_run: bool = False,
    limit: int | None = None,
    progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    year, season = validate_season(year, season)
    report = progress or (lambda _message: None)
    report("Connecting to MongoDB...")
    client = MongoClient(mongo_uri)
    collection = client.anime.seasonals
    query: dict[str, Any] = season_scope(year, season)
    if missing_only:
        query = {
            "$and": [
                query,
                {"$or": [{"score": None}, {"score": {"$exists": False}}]},
            ]
        }

    report(f"Finding anime for {season} {year}...")
    ids = sorted(int(value) for value in collection.distinct("id", query) if value)
    if limit is not None:
        ids = ids[:limit]
    report(f"Selected {len(ids)} anime record(s).")
    summary: dict[str, Any] = {
        "selected": len(ids),
        "updated": 0,
        "failed": 0,
        "dry_run": dry_run,
        "errors": [],
    }
    if dry_run:
        summary["mal_ids"] = ids
        client.close()
        return summary

    mal = MalApiClient(mal_client_id)
    episode_path = f"reddit_karma.{year}.{season}"
    try:
        for position, mal_id in enumerate(ids, start=1):
            prefix = f"[{position}/{len(ids)}]"
            try:
                report(f"{prefix} Fetching MAL {mal_id}...")
                data = mal.fetch_score(mal_id, progress=report)
                now = datetime.now(timezone.utc)
                statistic = {
                    "score": data.get("mean"),
                    "members": data.get("num_list_users"),
                    "scoring_members": data.get("num_scoring_users"),
                    "extra_stats": (data.get("statistics") or {}).get("status"),
                    "captured_at": now,
                }
                collection.update_one(
                    {"id": mal_id},
                    {
                        "$set": {
                            "score": data.get("mean"),
                            "members": data.get("num_list_users"),
                            "mal_updated_at": now,
                        }
                    },
                )
                if week is not None:
                    collection.update_one(
                        {
                            "id": mal_id,
                            episode_path: {"$elemMatch": {"week_id": week}},
                        },
                        {"$set": {f"{episode_path}.$[episode].mal_stats": statistic}},
                        array_filters=[{"episode.week_id": week}],
                    )
                summary["updated"] += 1
                title = data.get("title") or f"MAL {mal_id}"
                report(
                    f"{prefix} Updated {title}: "
                    f"score={data.get('mean')}, members={data.get('num_list_users')}"
                )
                time.sleep(0.25)
            except Exception as error:
                summary["failed"] += 1
                summary["errors"].append(f"{mal_id}: {error}")
                report(f"{prefix} Failed MAL {mal_id}: {error}")
    finally:
        client.close()
    return summary


def fetch_holo_catalog(
    *, year: int, season: str, url_template: str = DEFAULT_HOLO_URL
) -> tuple[str, dict[int, list[dict[str, str]]]]:
    year, season = validate_season(year, season)
    url = url_template.format(year=year, season=season)
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    catalog: dict[int, list[dict[str, str]]] = {}
    for entry in yaml.safe_load_all(response.text):
        if not isinstance(entry, dict):
            continue
        mal_id = extract_mal_id((entry.get("info") or {}).get("mal"))
        if mal_id is not None:
            catalog[mal_id] = normalize_stream_offers(entry.get("streams"))
    return url, catalog


def fetch_anilist_catalog(
    mal_ids: list[int], *, chunk_size: int = 25
) -> tuple[str, dict[int, list[dict[str, str]]]]:
    """Fetch legal streaming links for specific MAL IDs in small GraphQL batches."""
    catalog: dict[int, list[dict[str, str]]] = {}
    unique_ids = sorted(set(int(mal_id) for mal_id in mal_ids))
    for start in range(0, len(unique_ids), chunk_size):
        chunk = unique_ids[start : start + chunk_size]
        selections = "\n".join(
            f"m{mal_id}: Media(idMal: {mal_id}, type: ANIME) {{ "
            "idMal externalLinks { url site type isDisabled } }"
            for mal_id in chunk
        )
        response = requests.post(
            ANILIST_API_URL,
            json={"query": f"query {{\n{selections}\n}}"},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("errors"):
            raise RuntimeError(f"AniList GraphQL error: {payload['errors']}")
        for media in (payload.get("data") or {}).values():
            if not media or media.get("idMal") is None:
                continue
            catalog[int(media["idMal"])] = normalize_anilist_links(
                media.get("externalLinks")
            )
    return ANILIST_API_URL, catalog


def backfill_missing_streams(
    *,
    mongo_uri: str,
    year: int,
    season: str,
    overwrite: bool = False,
    dry_run: bool = False,
    limit: int | None = None,
    url_template: str = DEFAULT_HOLO_URL,
) -> dict[str, Any]:
    year, season = validate_season(year, season)
    client = MongoClient(mongo_uri)
    collection = client.anime.seasonals
    query: dict[str, Any] = season_scope(year, season)
    if not overwrite:
        query = {
            "$and": [
                query,
                {
                    "$or": [
                        {"streams": None},
                        {"streams": {"$exists": False}},
                        {"streams": {}},
                        {"streams": []},
                        {"streams": ""},
                    ]
                },
            ]
        }

    shows = list(
        collection.find(query, {"_id": 0, "id": 1, "title": 1}).sort("id", 1)
    )
    if limit is not None:
        shows = shows[:limit]
    selected_ids = [int(show["id"]) for show in shows]

    catalog: dict[int, list[dict[str, str]]] = {}
    source_by_id: dict[int, str] = {}
    sources: list[str] = []
    try:
        holo_url, holo_catalog = fetch_holo_catalog(
            year=year, season=season, url_template=url_template
        )
        sources.append(holo_url)
        for mal_id, offers in holo_catalog.items():
            if offers:
                catalog[mal_id] = offers
                source_by_id[mal_id] = holo_url
    except requests.HTTPError as error:
        if error.response is None or error.response.status_code != 404:
            client.close()
            raise

    missing_ids = [mal_id for mal_id in selected_ids if not catalog.get(mal_id)]
    try:
        if missing_ids:
            anilist_url, anilist_catalog = fetch_anilist_catalog(missing_ids)
            sources.append(anilist_url)
            for mal_id, offers in anilist_catalog.items():
                if offers:
                    catalog[mal_id] = offers
                    source_by_id[mal_id] = anilist_url
    except Exception:
        client.close()
        raise

    summary: dict[str, Any] = {
        "selected": len(shows),
        "catalogued": len(catalog),
        "updated": 0,
        "without_offer": 0,
        "dry_run": dry_run,
        "sources": sources,
        "mal_ids": [],
    }
    try:
        for show in shows:
            mal_id = int(show["id"])
            offers = catalog.get(mal_id) or []
            if not offers:
                summary["without_offer"] += 1
                continue
            summary["mal_ids"].append(mal_id)
            if dry_run:
                continue
            primary = offers[0]
            collection.update_one(
                {"id": mal_id},
                {
                    "$set": {
                        "streams": {
                            "name": primary["provider"],
                            "service": primary["name"],
                            "url": primary["url"],
                            "logo": None,
                        },
                        "stream_offers": offers,
                        "streams_updated_at": datetime.now(timezone.utc),
                        "streaming_source": source_by_id[mal_id],
                    }
                },
            )
            summary["updated"] += 1
    finally:
        client.close()
    return summary
