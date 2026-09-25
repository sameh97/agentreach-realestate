"""
Saved searches — every search a user runs is stored in Mongo and scoped to them.

GET    /api/searches        → the user's searches, newest first (summaries only)
GET    /api/searches/{id}   → one search with its full event log and all leads
DELETE /api/searches/{id}   → delete one search
"""
from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app import db
from app.auth import current_user

router = APIRouter(prefix="/api/searches", tags=["searches"])

# Heavy fields left out of list views
SUMMARY_PROJECTION = {"events": 0, "leads": 0}


def parse_id(search_id: str) -> ObjectId:
    try:
        return ObjectId(search_id)
    except (InvalidId, TypeError):
        raise HTTPException(404, "Search not found")


def _iso(dt):
    return dt.isoformat() if dt else None


def serialize_search(doc: dict, full: bool = False) -> dict:
    sid = str(doc["_id"])
    done = doc.get("status") == "done"
    out = {
        "id":                 sid,
        "query":              doc.get("query", ""),
        "status":             doc.get("status", "queued"),
        "location":           doc.get("location", ""),
        "lead_count":         doc.get("lead_count", 0),
        "high_quality_count": doc.get("high_quality_count", 0),
        "verified_count":     doc.get("verified_count", 0),
        "error":              doc.get("error", ""),
        "created_at":         _iso(doc.get("created_at")),
        "finished_at":        _iso(doc.get("finished_at")),
        "csv_url":            f"/api/leads/download/{sid}?format=csv"  if done else None,
        "xlsx_url":           f"/api/leads/download/{sid}?format=xlsx" if done else None,
    }
    if full:
        out["events"] = doc.get("events", [])
        out["leads"]  = doc.get("leads", [])
    return out


async def get_owned_search(search_id: str, user: dict, projection: dict | None = None) -> dict:
    doc = await db.searches().find_one({"_id": parse_id(search_id), "user_id": user["_id"]}, projection)
    if doc is None:
        raise HTTPException(404, "Search not found")
    return doc


@router.get("")
async def list_searches(
    limit: int = Query(50, ge=1, le=200),
    user:  dict = Depends(current_user),
):
    cursor = (db.searches()
              .find({"user_id": user["_id"]}, SUMMARY_PROJECTION)
              .sort("created_at", -1)
              .limit(limit))
    return [serialize_search(d) async for d in cursor]


@router.get("/{search_id}")
async def get_search(search_id: str, user: dict = Depends(current_user)):
    return serialize_search(await get_owned_search(search_id, user), full=True)


@router.delete("/{search_id}", status_code=204)
async def delete_search(search_id: str, user: dict = Depends(current_user)):
    res = await db.searches().delete_one({"_id": parse_id(search_id), "user_id": user["_id"]})
    if res.deleted_count == 0:
        raise HTTPException(404, "Search not found")
    return Response(status_code=204)
