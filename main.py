"""
Revoda Election Incident Dashboard — Backend API
EiE Nigeria · Civic Intelligence Platform

Run: uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import asyncpg
import redis.asyncio as aioredis
import json
import hashlib
import os
import uuid
from datetime import datetime, timezone
from typing import Optional, List
from contextlib import asynccontextmanager

from models import (
    IncidentCreate, IncidentResponse, IncidentVerify,
    PartnerReport, AlertResponse, StatsResponse,
    HotspotResponse, PaginatedIncidents
)
from auth import verify_partner_token
from anonymizer import anonymize_reporter
from hotspot import detect_hotspots
from notifier import send_escalation_alert


# ── App lifecycle ──────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    app.state.db = await asyncpg.create_pool(
        dsn=os.getenv("DATABASE_URL", "postgresql://revoda:revoda@localhost/revoda"),
        min_size=5, max_size=20
    )
    app.state.redis = await aioredis.from_url(
        os.getenv("REDIS_URL", "redis://localhost:6379"),
        decode_responses=True
    )
    app.state.ws_connections: List[WebSocket] = []
    yield
    # Shutdown
    await app.state.db.close()
    await app.state.redis.close()


app = FastAPI(
    title="Revoda Election Incident Dashboard API",
    description="Civic intelligence platform for election monitoring — EiE Nigeria",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://revoda.eienigeria.org", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer(auto_error=False)


# ── Helpers ────────────────────────────────────────────────────────────────────
async def get_db(request):
    return request.app.state.db

async def get_redis(request):
    return request.app.state.redis

async def broadcast_incident(app, incident: dict):
    """Push new incident to all connected WebSocket clients."""
    dead = []
    for ws in app.state.ws_connections:
        try:
            await ws.send_json({"event": "new_incident", "data": incident})
        except Exception:
            dead.append(ws)
    for ws in dead:
        app.state.ws_connections.remove(ws)


# ── CITIZEN INCIDENT REPORTING ─────────────────────────────────────────────────

@app.post("/api/v1/incidents", response_model=IncidentResponse, status_code=201,
          summary="Submit an election incident report (public, anonymous)")
async def submit_incident(
    incident: IncidentCreate,
    background_tasks: BackgroundTasks,
    request=None
):
    """
    Public endpoint — no authentication required.
    Reporter identity is anonymised before any storage occurs.
    """
    db = request.app.state.db
    redis = request.app.state.redis

    # Anonymise reporter before touching database
    anon_hash = anonymize_reporter(
        phone=incident.reporter_phone,
        device_id=incident.device_fingerprint
    )

    incident_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    async with db.acquire() as conn:
        row = await conn.fetchrow("""
            INSERT INTO incidents (
                id, category, sub_category, description,
                state, lga, ward, polling_unit_code,
                latitude, longitude,
                reporter_type, reporter_anon_hash,
                media_urls, status, created_at
            )
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,'unverified',$14)
            RETURNING *
        """,
            incident_id, incident.category, incident.sub_category,
            incident.description, incident.state, incident.lga,
            incident.ward, incident.polling_unit_code,
            incident.latitude, incident.longitude,
            incident.reporter_type, anon_hash,
            json.dumps(incident.media_urls or []), now
        )

    # Invalidate dashboard stats cache
    await redis.delete("stats:national", f"stats:{incident.state}")

    # Background: check if this creates a hotspot, send alerts
    background_tasks.add_task(
        run_hotspot_check, request.app, incident.state, incident.lga,
        incident.latitude, incident.longitude, incident.category
    )

    # Broadcast to live dashboard
    background_tasks.add_task(
        broadcast_incident, request.app, dict(row)
    )

    return IncidentResponse(**dict(row))


@app.get("/api/v1/incidents", response_model=PaginatedIncidents,
         summary="List incidents with filtering (public)")
async def list_incidents(
    state: Optional[str] = None,
    lga: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    per_page: int = 20,
    request=None
):
    db = request.app.state.db
    redis = request.app.state.redis

    # Try cache for common queries
    cache_key = f"incidents:{state}:{lga}:{category}:{status}:{page}"
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)

    filters, params = [], []
    if state:
        params.append(state); filters.append(f"state = ${len(params)}")
    if lga:
        params.append(lga); filters.append(f"lga = ${len(params)}")
    if category:
        params.append(category); filters.append(f"category = ${len(params)}")
    if status:
        params.append(status); filters.append(f"status = ${len(params)}")

    where = ("WHERE " + " AND ".join(filters)) if filters else ""
    offset = (page - 1) * per_page
    params += [per_page, offset]

    async with db.acquire() as conn:
        rows = await conn.fetch(f"""
            SELECT id, category, sub_category, description,
                   state, lga, ward, polling_unit_code,
                   latitude, longitude, status, created_at,
                   verified_at, media_urls
            FROM incidents {where}
            ORDER BY created_at DESC
            LIMIT ${len(params)-1} OFFSET ${len(params)}
        """, *params)

        total = await conn.fetchval(
            f"SELECT COUNT(*) FROM incidents {where}", *params[:-2]
        )

    result = {
        "incidents": [dict(r) for r in rows],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page
    }

    # Cache for 15 seconds (live data, short TTL)
    await redis.setex(cache_key, 15, json.dumps(result, default=str))
    return result


@app.get("/api/v1/incidents/{incident_id}", response_model=IncidentResponse)
async def get_incident(incident_id: str, request=None):
    db = request.app.state.db
    async with db.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM incidents WHERE id = $1", incident_id
        )
    if not row:
        raise HTTPException(404, "Incident not found")
    return IncidentResponse(**dict(row))


# ── PARTNER / ADMIN ENDPOINTS (authenticated) ──────────────────────────────────

@app.patch("/api/v1/incidents/{incident_id}/verify",
           summary="Verify or escalate an incident (partner/admin only)")
async def verify_incident(
    incident_id: str,
    body: IncidentVerify,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    request=None
):
    partner = verify_partner_token(credentials.credentials if credentials else None)
    if not partner:
        raise HTTPException(403, "Valid partner token required")

    db = request.app.state.db
    redis = request.app.state.redis

    async with db.acquire() as conn:
        row = await conn.fetchrow("""
            UPDATE incidents
            SET status = $1,
                verification_notes = $2,
                verified_by_partner = $3,
                verified_at = NOW()
            WHERE id = $4
            RETURNING *
        """, body.status, body.notes, partner["org_name"], incident_id)

    if not row:
        raise HTTPException(404, "Incident not found")

    # Invalidate caches
    await redis.delete(f"stats:{row['state']}", "stats:national")

    # If escalated, trigger alert pipeline
    if body.status == "escalated":
        await send_escalation_alert(dict(row), partner)

    return IncidentResponse(**dict(row))


@app.post("/api/v1/partners/report",
          summary="Bulk incident submission from CSO partners")
async def partner_bulk_report(
    report: PartnerReport,
    background_tasks: BackgroundTasks,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    request=None
):
    partner = verify_partner_token(credentials.credentials if credentials else None)
    if not partner:
        raise HTTPException(403, "Valid partner token required")

    db = request.app.state.db
    inserted = []

    async with db.acquire() as conn:
        async with conn.transaction():
            for inc in report.incidents:
                row = await conn.fetchrow("""
                    INSERT INTO incidents (
                        id, category, sub_category, description,
                        state, lga, ward, polling_unit_code,
                        latitude, longitude, reporter_type,
                        source_partner, status, created_at
                    )
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,'partner',$11,'unverified',NOW())
                    RETURNING id, category, state, lga
                """,
                    str(uuid.uuid4()), inc.category, inc.sub_category,
                    inc.description, inc.state, inc.lga, inc.ward,
                    inc.polling_unit_code, inc.latitude, inc.longitude,
                    partner["org_name"]
                )
                inserted.append(str(row["id"]))

    background_tasks.add_task(
        run_batch_hotspot_check, request.app, inserted
    )

    return {"accepted": len(inserted), "ids": inserted, "partner": partner["org_name"]}


# ── ANALYTICS & STATS ──────────────────────────────────────────────────────────

@app.get("/api/v1/stats", response_model=StatsResponse,
         summary="Live dashboard statistics")
async def get_stats(state: Optional[str] = None, request=None):
    db = request.app.state.db
    redis = request.app.state.redis

    cache_key = f"stats:{state or 'national'}"
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)

    where = "WHERE state = $1" if state else ""
    params = [state] if state else []

    async with db.acquire() as conn:
        totals = await conn.fetchrow(f"""
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE status = 'unverified') AS unverified,
                COUNT(*) FILTER (WHERE status = 'verified') AS verified,
                COUNT(*) FILTER (WHERE status = 'escalated') AS escalated
            FROM incidents {where}
        """, *params)

        by_category = await conn.fetch(f"""
            SELECT category, COUNT(*) AS count
            FROM incidents {where}
            GROUP BY category ORDER BY count DESC
        """, *params)

        by_state = await conn.fetch("""
            SELECT state, COUNT(*) AS count
            FROM incidents
            GROUP BY state ORDER BY count DESC LIMIT 10
        """)

    result = {
        "total": totals["total"],
        "unverified": totals["unverified"],
        "verified": totals["verified"],
        "escalated": totals["escalated"],
        "by_category": [dict(r) for r in by_category],
        "by_state": [dict(r) for r in by_state]
    }

    await redis.setex(cache_key, 30, json.dumps(result))
    return result


@app.get("/api/v1/hotspots", response_model=List[HotspotResponse],
         summary="Active incident hotspot clusters")
async def get_hotspots(radius_km: float = 5.0, min_incidents: int = 3, request=None):
    db = request.app.state.db
    redis = request.app.state.redis

    cache_key = f"hotspots:{radius_km}:{min_incidents}"
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)

    async with db.acquire() as conn:
        # PostGIS: cluster incidents by proximity
        rows = await conn.fetch("""
            SELECT
                ST_Y(ST_Centroid(ST_Collect(geom))) AS lat,
                ST_X(ST_Centroid(ST_Collect(geom))) AS lng,
                COUNT(*) AS incident_count,
                MAX(state) AS state,
                MAX(lga) AS lga,
                array_agg(DISTINCT category) AS categories,
                MAX(created_at) AS latest_incident
            FROM (
                SELECT geom, state, lga, category, created_at,
                    ST_ClusterDBSCAN(geom, eps := $1/111.0, minpoints := $2)
                    OVER () AS cluster_id
                FROM incidents
                WHERE created_at > NOW() - INTERVAL '24 hours'
                AND latitude IS NOT NULL
            ) clustered
            WHERE cluster_id IS NOT NULL
            GROUP BY cluster_id
            HAVING COUNT(*) >= $2
            ORDER BY incident_count DESC
        """, radius_km, min_incidents)

    result = [dict(r) for r in rows]
    await redis.setex(cache_key, 60, json.dumps(result, default=str))
    return result


@app.get("/api/v1/map/heatmap",
         summary="Heatmap data points for the Nigeria map")
async def get_heatmap(request=None):
    db = request.app.state.db
    async with db.acquire() as conn:
        rows = await conn.fetch("""
            SELECT latitude, longitude, COUNT(*) as weight
            FROM incidents
            WHERE latitude IS NOT NULL
            AND created_at > NOW() - INTERVAL '72 hours'
            GROUP BY latitude, longitude
        """)
    return [{"lat": r["latitude"], "lng": r["longitude"], "weight": r["weight"]}
            for r in rows]


# ── WEBSOCKET — LIVE FEED ──────────────────────────────────────────────────────

@app.websocket("/ws/live")
async def websocket_live_feed(websocket: WebSocket):
    await websocket.accept()
    websocket.app.state.ws_connections.append(websocket)
    try:
        while True:
            # Keep connection alive; data is pushed via broadcast_incident
            await websocket.receive_text()
    except WebSocketDisconnect:
        websocket.app.state.ws_connections.remove(websocket)


# ── BACKGROUND TASKS ───────────────────────────────────────────────────────────

async def run_hotspot_check(app, state, lga, lat, lng, category):
    """After each new incident, check if a hotspot has formed."""
    if lat is None or lng is None:
        return
    hotspots = await detect_hotspots(app.state.db, lat, lng, radius_km=3.0, min_count=3)
    if hotspots:
        alert = {
            "type": "hotspot_detected",
            "state": state, "lga": lga,
            "incident_count": hotspots[0]["count"],
            "category": category,
            "detected_at": datetime.now(timezone.utc).isoformat()
        }
        for ws in app.state.ws_connections:
            try:
                await ws.send_json({"event": "hotspot_alert", "data": alert})
            except Exception:
                pass


async def run_batch_hotspot_check(app, incident_ids: List[str]):
    """Hotspot check after bulk partner uploads."""
    async with app.state.db.acquire() as conn:
        rows = await conn.fetch("""
            SELECT latitude, longitude, state, lga, category
            FROM incidents WHERE id = ANY($1)
            AND latitude IS NOT NULL
        """, incident_ids)
    for row in rows:
        await run_hotspot_check(
            app, row["state"], row["lga"],
            row["latitude"], row["longitude"], row["category"]
        )
