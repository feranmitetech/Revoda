from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import uuid

app = FastAPI(
    title="Revoda Election Incident API",
    description="EiE Nigeria Election Monitoring Platform",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {
        "platform": "Revoda",
        "status": "live",
        "org": "EiE Nigeria",
        "version": "1.0.0"
    }

@app.get("/api/v1/stats")
def get_stats():
    return {
        "total": 1247,
        "unverified": 384,
        "verified": 863,
        "escalated": 37,
        "by_category": [
            {"category": "violence", "count": 218},
            {"category": "voting", "count": 341},
            {"category": "materials", "count": 187},
            {"category": "police", "count": 156},
            {"category": "counting", "count": 142},
            {"category": "results", "count": 203}
        ],
        "by_state": [
            {"state": "Rivers", "count": 182},
            {"state": "Lagos", "count": 154},
            {"state": "Kano", "count": 138},
            {"state": "Imo", "count": 117},
            {"state": "Borno", "count": 99}
        ]
    }

class IncidentCreate(BaseModel):
    category: str
    description: str
    state: str
    lga: Optional[str] = None
    polling_unit_code: Optional[str] = None
    reporter_type: Optional[str] = "citizen"

@app.post("/api/v1/incidents", status_code=201)
def submit_incident(incident: IncidentCreate):
    return {
        "id": str(uuid.uuid4()),
        "category": incident.category,
        "description": incident.description,
        "state": incident.state,
        "lga": incident.lga,
        "status": "unverified",
        "message": "Report received successfully"
    }

@app.get("/api/v1/incidents")
def list_incidents():
    return {
        "incidents": [],
        "total": 0,
        "page": 1,
        "per_page": 20,
        "pages": 0
    }
