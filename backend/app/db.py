"""
MongoDB connection
==================
Everything that must survive a restart lives here: users and their searches
(including every pipeline event and every scored lead).

Switching from the local Docker container to MongoDB Atlas is ONE env var:

  MONGO_URI=mongodb+srv://<user>:<password>@<cluster>.mongodb.net/?retryWrites=true&w=majority

Nothing else in the code changes — the driver handles SRV/TLS for Atlas.
"""
import os, asyncio, logging
from datetime import datetime, timedelta, timezone

from pymongo import AsyncMongoClient, ASCENDING, DESCENDING

logger = logging.getLogger(__name__)

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB  = os.getenv("MONGO_DB", "agentreach")

# A search still "running" after this long was interrupted (container restart,
# crash) — nothing will ever finish it, so it's marked failed on startup.
STALE_JOB_AFTER = timedelta(minutes=30)

_client: AsyncMongoClient | None = None


def get_db():
    global _client
    if _client is None:
        _client = AsyncMongoClient(MONGO_URI, tz_aware=True, serverSelectionTimeoutMS=5000)
    return _client[MONGO_DB]


def users():
    return get_db()["users"]


def searches():
    return get_db()["searches"]


async def ping() -> bool:
    try:
        await get_db().command("ping")
        return True
    except Exception:
        return False


async def init_db(attempts: int = 15, delay_sec: float = 2.0) -> None:
    """Create indexes + clean up interrupted jobs. Retries so the backend can
    start before the database is reachable (container still booting)."""
    for i in range(1, attempts + 1):
        try:
            await users().create_index([("email", ASCENDING)], unique=True)
            await searches().create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])

            cutoff = datetime.now(timezone.utc) - STALE_JOB_AFTER
            res = await searches().update_many(
                {"status": {"$in": ["queued", "running"]}, "created_at": {"$lt": cutoff}},
                {"$set": {"status": "failed", "error": "Interrupted — the server restarted mid-run"}},
            )
            if res.modified_count:
                logger.info(f"[db] marked {res.modified_count} interrupted searches as failed")

            logger.info(f"[db] connected to database {MONGO_DB!r}")
            return
        except Exception as e:
            logger.warning(f"[db] not ready (attempt {i}/{attempts}): {e}")
            await asyncio.sleep(delay_sec)
    logger.error("[db] could not reach MongoDB — auth and saved searches will fail until it is up")


async def close_db() -> None:
    global _client
    if _client is not None:
        await _client.close()
        _client = None
