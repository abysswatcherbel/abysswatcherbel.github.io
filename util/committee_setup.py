import os
from datetime import datetime
from pymongo import MongoClient
from util.logger_config import logger


def get_committee_data(filters=None, page=1, per_page=20):
    """
    Fetches and processes production committee data from MongoDB.

    Args:
        filters (dict, optional): Dictionary containing filtering criteria
        page (int, optional): Page number for pagination
        per_page (int, optional): Number of items per page

    Returns:
        dict: Dictionary containing processed committee data and metadata
    """
    # Default empty filters
    if filters is None:
        filters = {}

    # Connect to MongoDB
    client = MongoClient(os.getenv("MONGO_URI"))
    db = client.anime

    # Build MongoDB query from filters
    query = {}
    if "season" in filters and filters["season"] != "all":
        query["season"] = filters["season"]

    if "year" in filters and filters["year"] != "all":
        query["year"] = int(filters["year"])

    # Count total records for pagination
    total_shows = db.committee.count_documents(query)

    # Get committee data with pagination
    committee_cursor = db.committee.find(query).sort([("year", -1), ("season", 1)])
    committee_data = list(committee_cursor.skip((page - 1) * per_page).limit(per_page))

    # Get show IDs for efficient lookup
    show_ids = [show["id"] for show in committee_data if "id" in show]

    # Get all producers for lookup (using a dictionary for efficient access)
    producers = {}
    for producer in db.producers.find():
        if "id" in producer:
            producers[producer["id"]] = producer
        elif "mal_id" in producer:
            producers[producer["mal_id"]] = producer

    # Get seasonal anime data for the shows
    seasonal_shows = {
        show["id"]: show for show in db.seasonal.find({"id": {"$in": show_ids}})
    }

    # Process committees to add producer images and show details
    for show in committee_data:
        # Add show details from seasonal collection
        if "id" in show and show["id"] in seasonal_shows:
            seasonal_data = seasonal_shows[show["id"]]
            show["images"] = seasonal_data.get("images", {})
            show["title_english"] = seasonal_data.get("title_english", "")
            show["score"] = seasonal_data.get("score", None)
            show["studios"] = seasonal_data.get("studios", [])
            show["genres"] = seasonal_data.get("genres", [])
            show["streams"] = seasonal_data.get("streams", {})
            show["url"] = seasonal_data.get("url", "")

            # Add karma data if available
            reddit_karma = seasonal_data.get("reddit_karma", {})
            if reddit_karma and str(show.get("year", "")) in reddit_karma:
                year_karma = reddit_karma[str(show["year"])]
                if show.get("season", "") in year_karma:
                    season_karma = year_karma[show["season"]]
                    # Calculate average karma if multiple episodes exist
                    if season_karma:
                        karma_sum = sum(
                            episode.get("karma", 0)
                            for episode in season_karma
                            if "karma" in episode
                        )
                        karma_count = len([ep for ep in season_karma if "karma" in ep])
                        if karma_count > 0:
                            show["average_karma"] = round(karma_sum / karma_count, 2)

        # Process committee members
        if "committee" in show:
            enriched_committee = []
            for producer in show["committee"]:
                if "id" in producer:
                    producer_id = producer["id"]
                    if producer_id in producers:
                        # Merge producer info with committee entry
                        enriched_producer = producer.copy()

                        # Add producer image
                        producer_images = producers[producer_id].get("images", {})
                        if producer_images and "jpg" in producer_images:
                            enriched_producer["image"] = producer_images["jpg"].get(
                                "image_url", ""
                            )

                        # Add other producer details
                        enriched_producer["about"] = producers[producer_id].get(
                            "about", ""
                        )
                        enriched_producer["established"] = producers[producer_id].get(
                            "established", ""
                        )
                        enriched_producer["favorites"] = producers[producer_id].get(
                            "favorites", 0
                        )
                        enriched_producer["titles"] = producers[producer_id].get(
                            "titles", []
                        )

                        enriched_committee.append(enriched_producer)
                    else:
                        # Producer not found in producers collection
                        enriched_committee.append(producer)
                else:
                    # Producer doesn't have an ID
                    enriched_committee.append(producer)

            # Replace original committee list with enriched one
            show["committee"] = enriched_committee

    # Get distinct seasons and years for filters
    all_seasons = db.committee.distinct("season")
    all_years = sorted(db.committee.distinct("year"), reverse=True)

    client.close()

    return {
        "shows": committee_data,
        "total_shows": total_shows,
        "seasons": all_seasons,
        "years": all_years,
        "page": page,
        "per_page": per_page,
        "total_pages": (total_shows + per_page - 1) // per_page,
    }


def get_producer_details(producer_id):
    """
    Get detailed information about a specific producer.

    Args:
        producer_id (int): The ID of the producer

    Returns:
        dict: Producer details including shows they've worked on
    """
    client = MongoClient(os.getenv("MONGO_URI"))
    db = client.anime

    # Get producer details
    producer = db.producers.find_one({"id": producer_id})
    if not producer:
        producer = db.producers.find_one({"mal_id": producer_id})

    if not producer:
        client.close()
        return None

    # Find all shows this producer was involved in
    shows = []
    for committee in db.committee.find({"committee.id": producer_id}):
        show_id = committee.get("id")
        if show_id:
            # Get additional show details from seasonal collection
            seasonal_data = db.seasonal.find_one({"id": show_id})
            if seasonal_data:
                show_info = {
                    "id": show_id,
                    "title": committee.get("title", ""),
                    "title_english": seasonal_data.get("title_english", ""),
                    "year": committee.get("year", ""),
                    "season": committee.get("season", ""),
                    "images": seasonal_data.get("images", {}),
                    "score": seasonal_data.get("score", None),
                }

                # Check if this producer was the main producer
                if committee.get("main_producer", {}).get("id") == producer_id:
                    show_info["is_main_producer"] = True

                shows.append(show_info)

    # Sort shows by year and season, most recent first
    shows.sort(key=lambda x: (x.get("year", 0), x.get("season", "")), reverse=True)

    result = {
        "producer": producer,
        "shows": shows,
        "show_count": len(shows),
        "main_producer_count": sum(
            1 for show in shows if show.get("is_main_producer", False)
        ),
    }

    client.close()
    return result
