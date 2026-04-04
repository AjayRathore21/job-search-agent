"""
MongoDB connection singleton.
DB name is read directly from the MONGODB_URI connection string.
Both this agent service and the main backend use the same URI → same DB.
"""

import os
import logging
from pymongo import MongoClient
from pymongo.database import Database

logger = logging.getLogger(__name__)

_client: MongoClient | None = None
_db: Database | None = None


def get_db() -> Database:
    """
    Returns the shared MongoDB database instance.
    The database name is inferred from the URI (e.g. .../job_search_agent).
    Creates the connection on first call.
    """
    global _client, _db

    if _db is not None:
        return _db

    mongo_uri = os.environ.get("MONGODB_URI")
    if not mongo_uri:
        raise EnvironmentError("MONGODB_URI is not set in .env")

    _client = MongoClient(mongo_uri)

    # Reads DB name directly from the URI — no separate env var needed
    _db = _client.get_default_database()

    logger.info(f"✅ Connected to MongoDB: database='{_db.name}'")
    _ensure_indexes(_db)

    return _db


def _ensure_indexes(db: Database):
    """Create useful indexes if they don't already exist."""
    try:
        db["excel_results"].create_index([("user_id", 1), ("created_at", -1)])
        db["scheduled_jobs"].create_index([("user_id", 1)])
        db["user_memory"].create_index([("user_id", 1)], unique=True)
        logger.info("✅ MongoDB indexes ensured.")
    except Exception as e:
        logger.warning(f"Could not ensure indexes: {e}")

