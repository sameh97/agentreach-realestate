"""
Lead generation jobs — all endpoints require a logged-in user.

POST /api/leads/generate          → start job, returns job_id (= saved search id)
GET  /api/leads/stream/{job_id}   → SSE live progress
GET  /api/leads/status/{job_id}   → JSON polling fallback
GET  /api/leads/download/{job_id} → file download (?format=csv|xlsx)

Job state lives in MongoDB, not process memory: the worker that runs a job
writes each event to the search document, and whichever worker serves the
SSE stream reads them back. That keeps `uvicorn --workers N` (or several
replicas) consistent, and every finished search stays in the user's history.
"""
import os, json, asyncio, logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field, field_validator

from app import db
from app.auth import current_user
from app.agents.graph import lead_graph
from app.agents.state import LeadState
from app.api.searches import get_owned_search, parse_id, serialize_search
from app.nodes.lead_scorer import export_filename, leads_to_csv_bytes, leads_to_xlsx_bytes

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/leads", tags=["leads"])

MAX_RESULTS_CAP = int(os.getenv("MAX_RESULTS_CAP", "500"))
# Searches per user per rolling 24h — each run spends API quota. 0 = unlimited.
DAILY_SEARCH_LIMIT = int(os.getenv("DAILY_SEARCH_LIMIT", "0"))

# Fields included in the lead preview sent with the score_leads event
_PREVIEW_FIELDS = ("name", "primary_email", "score", "team_size", "specializations")


class GenerateRequest(BaseModel):
    query:       str
    max_results: int = Field(100, ge=1)
    max_retries: int = Field(3, ge=0, le=5)

    @field_validator("max_results")
    @classmethod
    def _cap(cls, v: int) -> int:
        return min(v, MAX_RESULTS_CAP)  # clamp, don't reject — the UI doesn't know the cap

    @field_validator("query")
    @classmethod
    def _query(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Query cannot be empty")
        return v[:300]


class JobCreated(BaseModel):
    job_id:     str
    stream_url: str
    status_url: str


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _bson_safe(value):
    """Round-trip through JSON so graph output (sets, numpy, etc.) stores cleanly."""
    return json.loads(json.dumps(value, default=str))


# ── Background task ───────────────────────────────────────────────────────────

async def _run_job(search_id, req: GenerateRequest):
    job_id = str(search_id)
    col    = db.searches()

    async def push(node: str, set_fields: dict | None = None, **data):
        update = {"$push": {"events": _bson_safe({"node": node, "ts": _now().isoformat(), **data})}}
        if set_fields:
            update["$set"] = set_fields
        await col.update_one({"_id": search_id}, update)

    try:
        await col.update_one({"_id": search_id}, {"$set": {"status": "running", "started_at": _now()}})
        await push("start", message=f'Starting: "{req.query}"')

        initial: LeadState = {
            "messages": [], "raw_query": req.query,
            "business_type": "", "location": "", "radius_km": 25.0,
            "enrichment_reqs": [], "max_results": req.max_results,
            "specialization_filter": "none", "team_filter": "none",
            "raw_businesses": [], "scrape_errors": [],
            "enriched_leads": [], "enrichment_errors": [],
            "re_signal_errors": [],
            "verified_leads": [], "verification_errors": [],
            "scored_leads": [], "final_csv_path": "", "final_xlsx_path": "",
            "retry_count": 0, "max_retries": req.max_retries,
            "status": "running", "error_message": "",
        }

        # The graph is synchronous, so it runs in a worker thread and hands each
        # node's output back to the event loop, where it is written to Mongo.
        loop  = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue()

        def _run():
            try:
                for chunk in lead_graph.stream(initial, config={"configurable": {"thread_id": job_id}}):
                    loop.call_soon_threadsafe(queue.put_nowait, ("chunk", chunk))
                loop.call_soon_threadsafe(queue.put_nowait, ("end", None))
            except Exception as e:
                loop.call_soon_threadsafe(queue.put_nowait, ("error", e))

        worker = loop.run_in_executor(None, _run)
        final  = None

        while True:
            kind, payload = await queue.get()
            if kind == "error":
                raise payload
            if kind == "end":
                break

            for node_name, s in payload.items():
                if node_name == "parse_query":
                    await push("parse_query",
                               set_fields={"location": s.get("location", "")},
                               message="Query understood",
                               business_type=s.get("business_type"),
                               location=s.get("location"),
                               radius_km=s.get("radius_km"))

                elif node_name == "scrape_maps":
                    n = len(s.get("raw_businesses", []))
                    advisories = s.get("scrape_errors", [])
                    msg = f"Found {n} businesses on Google Maps"
                    if advisories:
                        msg += f" — note: {advisories[0]}"
                    await push("scrape_maps", message=msg, count=n)

                elif node_name == "enrich_websites":
                    n = len(s.get("enriched_leads", []))
                    await push("enrich_websites", message=f"Enriched {n} businesses with emails", count=n)

                elif node_name == "enrich_re_signals":
                    el = s.get("enriched_leads", [])
                    brokerages = sum(1 for l in el if l.get("team_size") == "brokerage")
                    await push("enrich_re_signals",
                               message=f"Scanned sites — {brokerages} brokerages detected",
                               count=len(el), brokerages=brokerages)

                elif node_name == "verify_emails":
                    vl = s.get("verified_leads", [])
                    ok = sum(1 for l in vl if l.get("email_valid"))
                    await push("verify_emails",
                               message=f"Verified {ok}/{len(vl)} emails as deliverable",
                               verified=ok, total=len(vl))

                elif node_name == "score_leads":
                    sl   = s.get("scored_leads", [])
                    high = sum(1 for l in sl if l.get("score", 0) >= 70)
                    await push("score_leads",
                               message=f"Scored {len(sl)} leads — {high} high-quality",
                               total=len(sl), high_quality=high,
                               preview=[{k: l.get(k) for k in _PREVIEW_FIELDS} for l in sl[:5]])

                elif node_name == "deliver":
                    await push("deliver",
                               message="Files ready for download",
                               csv_url=f"/api/leads/download/{job_id}?format=csv",
                               xlsx_url=f"/api/leads/download/{job_id}?format=xlsx")
                    final = s

                elif node_name == "fail":
                    message = s.get("error_message", "Pipeline failed")
                    await push("fail",
                               set_fields={"status": "failed", "error": message, "finished_at": _now()},
                               message=message)
                    return

        await worker

        if final is None:
            raise RuntimeError("Pipeline ended without delivering results")

        leads = _bson_safe(final.get("scored_leads", []))
        count = len(leads)
        # Status and the "done" event are written in one update, so a stream
        # reader never sees status=done without the done event.
        await push("done",
                   set_fields={
                       "status":             "done",
                       "finished_at":        _now(),
                       "leads":              leads,
                       "lead_count":         count,
                       "high_quality_count": sum(1 for l in leads if l.get("score", 0) >= 70),
                       "verified_count":     sum(1 for l in leads if l.get("email_verified")),
                   },
                   message=f"{count} verified leads ready!",
                   lead_count=count,
                   csv_url=f"/api/leads/download/{job_id}?format=csv",
                   xlsx_url=f"/api/leads/download/{job_id}?format=xlsx")

    except Exception as e:
        logger.exception(f"[job {job_id}] Fatal: {e}")
        await push("fail",
                   set_fields={"status": "failed", "error": str(e), "finished_at": _now()},
                   message=str(e))


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/generate", response_model=JobCreated)
async def generate(req: GenerateRequest, bg: BackgroundTasks, user: dict = Depends(current_user)):
    # One running search per user — each run spends paid API quota.
    running = await db.searches().find_one({
        "user_id":    user["_id"],
        "status":     {"$in": ["queued", "running"]},
        "created_at": {"$gt": _now() - db.STALE_JOB_AFTER},
    }, {"_id": 1})
    if running:
        raise HTTPException(409, "You already have a search running — wait for it to finish")

    if DAILY_SEARCH_LIMIT:
        recent = await db.searches().count_documents({
            "user_id":    user["_id"],
            "created_at": {"$gt": _now() - timedelta(days=1)},
        })
        if recent >= DAILY_SEARCH_LIMIT:
            raise HTTPException(429, f"Daily limit reached ({DAILY_SEARCH_LIMIT} searches per 24 hours) — try again tomorrow")

    res = await db.searches().insert_one({
        "user_id":    user["_id"],
        "query":      req.query,
        "status":     "queued",
        "location":   "",
        "events":     [],
        "leads":      [],
        "lead_count": 0,
        "created_at": _now(),
    })
    jid = str(res.inserted_id)
    bg.add_task(_run_job, res.inserted_id, req)
    return JobCreated(
        job_id=jid,
        stream_url=f"/api/leads/stream/{jid}",
        status_url=f"/api/leads/status/{jid}",
    )


@router.get("/stream/{job_id}")
async def stream(job_id: str, user: dict = Depends(current_user)):
    await get_owned_search(job_id, user, {"_id": 1})
    sid = parse_id(job_id)

    async def gen():
        seen, idle = 0, 0.0
        batch = 200
        while True:
            doc = await db.searches().find_one(
                {"_id": sid}, {"status": 1, "events": {"$slice": [seen, batch]}},
            )
            if doc is None:   # deleted mid-run
                yield f"data: {json.dumps({'node': 'end', 'status': 'failed'})}\n\n"
                break

            events = doc.get("events", [])
            for ev in events:
                yield f"data: {json.dumps(ev)}\n\n"
            seen += len(events)

            if len(events) == batch:
                continue   # more buffered events — read them before sleeping
            if doc["status"] in ("done", "failed"):
                yield f"data: {json.dumps({'node': 'end', 'status': doc['status']})}\n\n"
                break

            idle = 0.0 if events else idle + 0.5
            if idle >= 15:   # keep proxies from closing a quiet connection
                yield ": ping\n\n"
                idle = 0.0
            await asyncio.sleep(0.5)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})


@router.get("/status/{job_id}")
async def status(job_id: str, user: dict = Depends(current_user)):
    return serialize_search(await get_owned_search(job_id, user, {"events": 0, "leads": 0}))


@router.get("/download/{job_id}")
async def download(job_id: str, format: str = "csv", user: dict = Depends(current_user)):
    doc = await get_owned_search(job_id, user, {"events": 0})
    if doc["status"] != "done":
        raise HTTPException(400, f"Job not complete (status: {doc['status']})")

    leads, created = doc.get("leads", []), doc["created_at"]
    if format == "xlsx":
        body = await asyncio.to_thread(leads_to_xlsx_bytes, leads)
        name = export_filename(doc.get("location", ""), created, "xlsx")
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        body = leads_to_csv_bytes(leads)
        name = export_filename(doc.get("location", ""), created, "csv")
        media = "text/csv"

    return Response(body, media_type=media,
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})
