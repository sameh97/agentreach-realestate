"""
AgentReach — FastAPI entrypoint
================================
Verified real estate agent & brokerage leads for vendors selling INTO
real estate (coaching, E&O insurance, marketing/CRM tools, title &
escrow, loan-officer referral partners). Single vertical, on purpose.

Auth      → app/api/auth_routes.py   (/api/auth/*)
Leads     → app/api/leads.py         (/api/leads/*)
Searches  → app/api/searches.py      (/api/searches/*)
GET /api/health                      → health check
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import db
from app.api import auth_routes, leads, searches

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(name)s  %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    await db.init_db()
    yield
    await db.close_db()


app = FastAPI(title="AgentReach API — Real Estate Lead Finder", version="1.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten in production
    allow_credentials=False,  # auth is a Bearer header, not cookies
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],  # lets the browser read download filenames
)

app.include_router(auth_routes.router)
app.include_router(leads.router)
app.include_router(searches.router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "db": await db.ping()}
