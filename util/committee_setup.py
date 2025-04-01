import os
from datetime import datetime
from pymongo import MongoClient
from util.logger_config import logger
import json


def get_committee_data(filters=None):
    """
    Fetches and processes production committee data from MongoDB.
    Simplified version without pagination and with minimal producer details.

    Args:
        filters (dict, optional): Dictionary containing filtering criteria
            - season: Filter by anime season (winter, spring, summer, fall)
            - year: Filter by year

    Returns:
        dict: Dictionary containing processed committee data
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

    # Get committee data
    committee_cursor = db.committees.find(query, {"_id": 0}).sort(
        [("year", -1), ("season", 1)]
    )
    committee_data = list(committee_cursor)

    # Get all show IDs for efficient lookup
    show_ids = [show["id"] for show in committee_data if "id" in show]

    # Get all producers for lookup
    producers = {}
    for producer in db.producers.find({}, {"_id": 0}):
        producer_id = producer.get("id") or producer.get("mal_id")
        if producer_id:
            producers[producer_id] = producer

    # Get seasonal data for shows
    all_seasonal_shows = {}
    for show in db.seasonals.find({"id": {"$in": show_ids}}, {"_id": 0}):
        if "id" in show:
            all_seasonal_shows[show["id"]] = show

    # Process committees to add producer images and show details
    for show in committee_data:
        # Add show details from seasonal collection
        if "id" in show and show["id"] in all_seasonal_shows:
            seasonal_data = all_seasonal_shows[show["id"]]
            show["images"] = seasonal_data.get("images", {})
            show["title_english"] = seasonal_data.get("title_english", "")
            show["score"] = seasonal_data.get("score", None)
            show["streams"] = seasonal_data.get("streams", {})
            show["url"] = seasonal_data.get("url", "")

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

                        # Add basic producer details
                        enriched_producer["established"] = producers[producer_id].get(
                            "established", ""
                        )
                        enriched_producer["favorites"] = producers[producer_id].get(
                            "favorites", 0
                        )
                        enriched_producer["titles"] = producers[producer_id].get(
                            "titles", []
                        )

                        # Add a short about section (truncated)
                        about = producers[producer_id].get("about", "")
                        if about:
                            enriched_producer["about"] = about

                        enriched_committee.append(enriched_producer)
                    else:
                        # Producer not found in producers collection
                        enriched_committee.append(producer)
                else:
                    # Producer doesn't have an ID
                    enriched_committee.append(producer)

            # Replace original committee list with enriched one
            show["committee"] = enriched_committee

    client.close()
    logger.debug(
        f"Fetched {len(committee_data)} committee entries with filters: {filters}. Sample: {json.dumps(committee_data[0], indent=4) if committee_data else 'No data found.'}"
    )

    with open(
        os.path.join("static", "data", "committees.json"), "w"
    ) as f:
        json.dump(committee_data, f, indent=4)

    return {
        "shows": committee_data,
    }
