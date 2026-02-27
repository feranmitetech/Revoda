"""
Revoda — Hotspot Detection Engine

Uses PostGIS DBSCAN clustering to identify geographic clusters
of incidents that warrant escalation alerts.

Also compares against historical election data to flag
known problem locations.
"""

import asyncpg
from typing import List, Optional
from datetime import datetime, timezone, timedelta


async def detect_hotspots(
    db: asyncpg.Pool,
    lat: float,
    lng: float,
    radius_km: float = 3.0,
    min_count: int = 3,
    time_window_hours: int = 6,
) -> List[dict]:
    """
    Check if a new incident at (lat, lng) triggers a hotspot.
    Returns list of active clusters near this location.
    """
    async with db.acquire() as conn:
        rows = await conn.fetch("""
            SELECT
                COUNT(*) AS count,
                array_agg(DISTINCT category) AS categories,
                MAX(state) AS state,
                MAX(lga) AS lga,
                AVG(latitude) AS center_lat,
                AVG(longitude) AS center_lng
            FROM incidents
            WHERE ST_DWithin(
                ST_MakePoint(longitude, latitude)::geography,
                ST_MakePoint($1, $2)::geography,
                $3 * 1000  -- metres
            )
            AND created_at > NOW() - ($4 || ' hours')::INTERVAL
            AND status != 'dismissed'
            HAVING COUNT(*) >= $5
        """, lng, lat, radius_km, str(time_window_hours), min_count)

    return [dict(r) for r in rows]


async def detect_national_hotspots(
    db: asyncpg.Pool,
    radius_km: float = 5.0,
    min_count: int = 4,
    time_window_hours: int = 12,
) -> List[dict]:
    """
    Full national scan for hotspot clusters.
    Run periodically (every 5 min on election day).
    """
    async with db.acquire() as conn:
        rows = await conn.fetch("""
            WITH clustered AS (
                SELECT *,
                    ST_ClusterDBSCAN(
                        ST_MakePoint(longitude, latitude)::geography::geometry,
                        eps := $1 / 111.0,
                        minpoints := $2
                    ) OVER () AS cluster_id
                FROM incidents
                WHERE created_at > NOW() - ($3 || ' hours')::INTERVAL
                AND latitude IS NOT NULL
                AND status != 'dismissed'
            )
            SELECT
                cluster_id,
                COUNT(*) AS incident_count,
                AVG(latitude) AS center_lat,
                AVG(longitude) AS center_lng,
                MAX(state) AS state,
                MAX(lga) AS lga,
                array_agg(DISTINCT category) AS categories,
                COUNT(*) FILTER (WHERE category = 'violence') AS violence_count,
                MAX(created_at) AS latest_incident
            FROM clustered
            WHERE cluster_id IS NOT NULL
            GROUP BY cluster_id
            HAVING COUNT(*) >= $2
            ORDER BY incident_count DESC
        """, radius_km, min_count, str(time_window_hours))

    return [dict(r) for r in rows]


async def compare_historical_pattern(
    db: asyncpg.Pool,
    state: str,
    lga: str,
    category: str,
) -> Optional[dict]:
    """
    Check if this location + category matches a pattern from previous elections.
    Returns historical context if pattern found.
    """
    async with db.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT
                election_year,
                COUNT(*) AS historical_count,
                MAX(notes) AS pattern_description
            FROM historical_incidents
            WHERE state = $1
            AND lga = $2
            AND category = $3
            GROUP BY election_year
            ORDER BY election_year DESC
            LIMIT 1
        """, state, lga, category)

    if row and row["historical_count"] >= 3:
        return {
            "matched": True,
            "election_year": row["election_year"],
            "previous_count": row["historical_count"],
            "pattern_notes": row["pattern_description"],
            "message": (
                f"⚠ Pattern match: {row['historical_count']} similar incidents "
                f"reported in {lga}, {state} during {row['election_year']} elections."
            )
        }
    return None


def calculate_severity(incident_count: int, categories: List[str]) -> str:
    """Determine alert severity based on cluster composition."""
    CRITICAL_CATEGORIES = {"violence", "results_verification"}
    HIGH_CATEGORIES = {"vote_counting", "result_announcement"}

    if any(c in CRITICAL_CATEGORIES for c in categories) or incident_count >= 8:
        return "critical"
    if any(c in HIGH_CATEGORIES for c in categories) or incident_count >= 5:
        return "high"
    if incident_count >= 3:
        return "medium"
    return "low"
