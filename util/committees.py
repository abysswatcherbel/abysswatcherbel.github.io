import os
from pymongo import MongoClient
import json
from util.logger_config import logger


def get_committee_data():
    """
    Fetches and processes production committee data from MongoDB.
    Optimized version that handles the correct field mappings between collections.

    Returns:
        dict: Dictionary containing processed committee data
    """
    # Connect to MongoDB
    client = MongoClient(os.getenv("MONGO_URI"))
    db = client.anime

    logger.info("Setting up the committees data")
    # Basic pipeline to get committees with seasonal data
    committee_data = list(db.committees.find({},{"_id": 0}).sort([("year", -1), ("season", 1)]))

    # Get all committee member IDs for lookup
    all_producer_ids = set()
    for show in committee_data:
        if "committee" in show and isinstance(show["committee"], list):
            for member in show["committee"]:
                if "id" in member:
                    all_producer_ids.add(member["id"])

    # Get producer data
    producers_data = {}
    for producer in db.producers.find({"mal_id": {"$in": list(all_producer_ids)}}, {"_id": 0}):
        if "mal_id" in producer:
            producers_data[producer["mal_id"]] = producer

    # Get seasonal data
    show_ids = [show["id"] for show in committee_data if "id" in show]
    seasonal_data = {}
    for show in db.seasonals.find({"id": {"$in": show_ids}}, {"_id": 0}):
        if "id" in show:
            seasonal_data[show["id"]] = show

    # Enrich committee data with seasonal and producer info
    for show in committee_data:
        # Add seasonal data
        if "id" in show and show["id"] in seasonal_data:
            seasonal = seasonal_data[show["id"]]
            show["images"] = seasonal.get("images", {})
            show["title_english"] = seasonal.get("title_english", "")
            show["score"] = seasonal.get("score", None)
            show["streams"] = seasonal.get("streams", {})
            show["url"] = seasonal.get("url", "")
            show["studios"] = seasonal.get("studios", [])

        # Enrich committee members with producer data
        if "committee" in show and isinstance(show["committee"], list):
            enriched_committee = []
            for member in show["committee"]:
                if "id" in member and member["id"] in producers_data:
                    producer = producers_data[member["id"]]

                    # Create enriched member
                    enriched_member = member.copy()

                    # Add image URL if available
                    if "images" in producer and "jpg" in producer["images"]:
                        enriched_member["image"] = producer["images"]["jpg"].get("image_url", "")

                    # Add other producer details
                    enriched_member["established"] = producer.get("established", "")
                    enriched_member["favorites"] = producer.get("favorites", 0)
                    enriched_member["country"] = producer.get("country", "")

                    # Add flag URL if country is available
                    if enriched_member["country"]:
                        country_code = enriched_member["country"].lower()
                        enriched_member["flag"] = f"https://flagcdn.com/w20/{country_code}.webp"

                    enriched_committee.append(enriched_member)
                else:
                    # Keep the original member if no matching producer found
                    enriched_committee.append(member)

            # Replace original committee with enriched one
            show["committee"] = enriched_committee

    # Write the result to a JSON file
    with open(os.path.join("static", "data", "committees.json"), "w") as f:
        json.dump(committee_data, f, indent=4)

    client.close()

    return {
        "shows": committee_data
    }