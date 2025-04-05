# util/mongo_client.py
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.collection import Collection
import os
from contextlib import contextmanager
from util.logger_config import logger

# Singleton client
_mongo_client = None


def get_client() -> MongoClient:
    """
    Returns a MongoDB client instance (singleton pattern).
    """
    global _mongo_client
    if _mongo_client is None:
        mongo_uri = os.getenv("MONGO_URI")
        if not mongo_uri:
            raise ValueError("MONGO_URI environment variable is not set")
        _mongo_client = MongoClient(mongo_uri)
        logger.debug("MongoDB client initialized")
    return _mongo_client


def get_db(db_name="anime") -> Database:
    """
    Returns a specific database from the MongoDB client.
    """
    client = get_client()
    return client[db_name]


def get_collection(collection_name, db_name="anime") -> Collection:
    """
    Returns a specific collection from the specified database.
    """
    db = get_db(db_name)
    return db[collection_name]


@contextmanager
def mongo_session():
    """
    Context manager for MongoDB operations.
    Usage:
        with mongo_session() as db:
            # Use db.collection to query
    """
    client = get_client()
    try:
        db = client.anime
        yield db
    except Exception as e:
        logger.error(f"MongoDB error: {e}")
        raise
    finally:
        # We don't close the client here since it's a singleton
        pass


def close_connection():
    """
    Explicitly close the MongoDB connection.
    Call this when your application is shutting down.
    """
    global _mongo_client
    if _mongo_client:
        _mongo_client.close()
        _mongo_client = None
        logger.debug("MongoDB connection closed")
