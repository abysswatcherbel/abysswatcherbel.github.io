from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from bson.objectid import ObjectId


def connect_to_mongo(uri: str):
    """
    Connect to MongoDB using the provided URI.
    """
    try:
        client = MongoClient(uri)
        # Test the connection
        client.admin.command('ping')
        print("Connected to MongoDB")
        return client
    except ConnectionFailure as e:
        print(f"Could not connect to MongoDB: {e}")
        return None
    except Exception as e:
        print(f"An error occurred: {e}")
        return None

def validade_season(season: str):
    """
    Validate the season format.
    """
    if not isinstance(season, str):
        raise ValueError("Season must be a string")
    if len(season) != 7 or not season.startswith("S") or not season[1:].isdigit():
        raise ValueError("Invalid season format. Expected format: 'SXXXX'")
    return True