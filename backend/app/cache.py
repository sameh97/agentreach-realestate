"""
Lead cache
==========
The agents in a city are the same for every customer who searches it, so the
expensive work — the Maps search, scraping each agent's site, verifying each
email — is stored and reused instead of redone per search:

  maps_cache  one doc per location: the businesses Maps returned (MAPS_TTL)
  places      one doc per business (Google place_id), with field groups that
              each carry their own timestamp:
                contact   emails, WhatsApp, owner         (PLACE_TTL)
                signals   team size, specializations, …   (PLACE_TTL)
                verify    email verification result       (VERIFY_TTL)

The pipeline nodes are synchronous and run in a worker thread, so this uses
pymongo's sync client rather than the app's AsyncMongoClient. Every function
swallows its errors: a cache outage makes searches slower, never broken.
"""
import re, logging
from datetime import datetime, timedelta, timezone

from pymongo import MongoClient, UpdateOne

from app.db import MONGO_URI, MONGO_DB

logger = logging.getLogger(__name__)

MAPS_TTL   = timedelta(days=14)
PLACE_TTL  = timedelta(days=45)
VERIFY_TTL = timedelta(days=30)

CONTACT_FIELDS = ("emails", "primary_email", "owner_name", "owner_position", "whatsapp", "enriched")
SIGNAL_FIELDS  = ("team_size", "specializations", "license_detected", "idx_detected",
                  "testimonial_count", "years_in_business", "service_area_count", "recent_activity")
VERIFY_FIELDS  = ("email_valid", "email_verified", "email_catchall", "email_status",
                  "do_not_mail", "deliverability")

_client: MongoClient | None = None


def _db():
    global _client
    if _client is None:
        _client = MongoClient(MONGO_URI, tz_aware=True, serverSelectionTimeoutMS=3000)
    return _client[MONGO_DB]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _fresh(ts, ttl: timedelta) -> bool:
    return isinstance(ts, datetime) and _now() - ts < ttl


def place_key(b: dict) -> str:
    """Google's place_id when the source gives one, else name + phone digits."""
    if b.get("place_id"):
        return str(b["place_id"])
    phone = re.sub(r"\D", "", str(b.get("phone") or ""))
    return f"{str(b.get('name') or '').strip().lower()}|{phone}"


def location_key(location: str, country: str) -> str:
    loc = re.sub(r"\s+", " ", location.strip().lower())
    return f"{country.lower()}|{loc}"


# ── Maps results ──────────────────────────────────────────────────────────────

def get_maps(location: str, country: str, limit: int) -> list[dict] | None:
    """Cached businesses for this location, if fresh and fetched with a limit
    at least this large (a 20-result search can't serve a 100-result one)."""
    try:
        doc = _db()["maps_cache"].find_one({"_id": location_key(location, country)})
    except Exception as e:
        logger.warning(f"[cache] maps lookup failed: {e}")
        return None
    if doc and _fresh(doc.get("fetched_at"), MAPS_TTL) and doc.get("limit", 0) >= limit:
        return doc.get("businesses") or None
    return None


def save_maps(location: str, country: str, limit: int, businesses: list[dict]) -> None:
    if not businesses or all(b.get("source") == "demo" for b in businesses):
        return
    try:
        _db()["maps_cache"].replace_one(
            {"_id": location_key(location, country)},
            {"businesses": businesses, "limit": limit, "fetched_at": _now()},
            upsert=True,
        )
    except Exception as e:
        logger.warning(f"[cache] maps save failed: {e}")


# ── Per-business facts ────────────────────────────────────────────────────────

def get_places(businesses: list[dict]) -> dict[str, dict]:
    """place docs for these businesses, keyed by place_key."""
    keys = [place_key(b) for b in businesses]
    try:
        return {d["_id"]: d for d in _db()["places"].find({"_id": {"$in": keys}})}
    except Exception as e:
        logger.warning(f"[cache] places lookup failed: {e}")
        return {}


def cached_group(doc: dict | None, group: str, ttl: timedelta) -> dict | None:
    """The stored fields of one group, or None when missing or stale."""
    if doc and _fresh(doc.get(f"{group}_at"), ttl):
        return doc.get(group)
    return None


def save_group(leads: list[dict], group: str, fields: tuple[str, ...]) -> None:
    ops = [
        UpdateOne(
            {"_id": place_key(l)},
            {"$set": {group: {f: l.get(f) for f in fields}, f"{group}_at": _now(),
                      "name": l.get("name"), "website": l.get("website")}},
            upsert=True,
        )
        for l in leads if l.get("source") != "demo"
    ]
    if not ops:
        return
    try:
        _db()["places"].bulk_write(ops, ordered=False)
    except Exception as e:
        logger.warning(f"[cache] save {group} failed: {e}")
