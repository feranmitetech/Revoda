"""
Revoda — Pydantic data models
"""

from pydantic import BaseModel, field_validator, model_validator
from typing import Optional, List, Literal
from datetime import datetime
from enum import Enum


# ── Enums ──────────────────────────────────────────────────────────────────────

class IncidentCategory(str, Enum):
    OFFICIALS_ARRIVAL   = "electoral_officials_arrival"
    MATERIALS           = "material_availability"
    VOTING              = "voting_irregularity"
    COUNTING            = "vote_counting"
    RESULTS             = "result_announcement"
    VIOLENCE            = "violence"
    POLICE              = "police_behaviour"
    RESULTS_VERIFY      = "results_verification"


class IncidentStatus(str, Enum):
    UNVERIFIED  = "unverified"
    VERIFIED    = "verified"
    ESCALATED   = "escalated"
    DISMISSED   = "dismissed"


class ReporterType(str, Enum):
    CITIZEN     = "citizen"
    PARTY_AGENT = "party_agent"
    OBSERVER    = "observer"
    JOURNALIST  = "journalist"
    INEC        = "inec_official"
    PARTNER     = "partner"


NIGERIA_STATES = {
    "Abia","Adamawa","Akwa Ibom","Anambra","Bauchi","Bayelsa","Benue","Borno",
    "Cross River","Delta","Ebonyi","Edo","Ekiti","Enugu","FCT","Gombe","Imo",
    "Jigawa","Kaduna","Kano","Katsina","Kebbi","Kogi","Kwara","Lagos",
    "Nasarawa","Niger","Ogun","Ondo","Osun","Oyo","Plateau","Rivers",
    "Sokoto","Taraba","Yobe","Zamfara"
}


# ── Request Models ─────────────────────────────────────────────────────────────

class IncidentCreate(BaseModel):
    # Required
    category: IncidentCategory
    description: str
    state: str
    reporter_type: ReporterType

    # Optional location (at least state required)
    sub_category: Optional[str] = None
    lga: Optional[str] = None
    ward: Optional[str] = None
    polling_unit_code: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    # Media
    media_urls: Optional[List[str]] = []

    # These are anonymised immediately — never stored raw
    reporter_phone: Optional[str] = None
    device_fingerprint: Optional[str] = None

    @field_validator("description")
    @classmethod
    def desc_not_empty(cls, v):
        v = v.strip()
        if len(v) < 10:
            raise ValueError("Description must be at least 10 characters")
        if len(v) > 2000:
            raise ValueError("Description must be under 2000 characters")
        return v

    @field_validator("state")
    @classmethod
    def valid_state(cls, v):
        if v not in NIGERIA_STATES:
            raise ValueError(f"'{v}' is not a valid Nigerian state")
        return v

    @field_validator("latitude")
    @classmethod
    def valid_lat(cls, v):
        if v is not None and not (4.0 <= v <= 13.9):
            raise ValueError("Latitude out of Nigeria bounds (4.0 – 13.9)")
        return v

    @field_validator("longitude")
    @classmethod
    def valid_lng(cls, v):
        if v is not None and not (2.7 <= v <= 14.7):
            raise ValueError("Longitude out of Nigeria bounds (2.7 – 14.7)")
        return v

    @field_validator("reporter_phone")
    @classmethod
    def strip_phone(cls, v):
        """Phone is stripped immediately; only its hash survives."""
        return None  # Always nullified before model is used downstream

    model_config = {"use_enum_values": True}


class IncidentVerify(BaseModel):
    status: Literal["verified", "escalated", "dismissed"]
    notes: Optional[str] = None


class PartnerIncident(BaseModel):
    """Single incident in a bulk partner upload."""
    category: IncidentCategory
    sub_category: Optional[str] = None
    description: str
    state: str
    lga: Optional[str] = None
    ward: Optional[str] = None
    polling_unit_code: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    model_config = {"use_enum_values": True}


class PartnerReport(BaseModel):
    election_id: Optional[str] = None
    incidents: List[PartnerIncident]

    @field_validator("incidents")
    @classmethod
    def max_batch_size(cls, v):
        if len(v) > 500:
            raise ValueError("Batch upload limited to 500 incidents")
        return v


# ── Response Models ────────────────────────────────────────────────────────────

class IncidentResponse(BaseModel):
    id: str
    category: str
    sub_category: Optional[str] = None
    description: str
    state: str
    lga: Optional[str] = None
    ward: Optional[str] = None
    polling_unit_code: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    reporter_type: str
    status: str
    created_at: datetime
    verified_at: Optional[datetime] = None
    verified_by_partner: Optional[str] = None
    media_urls: Optional[List[str]] = []

    # Never expose: reporter_anon_hash, reporter_phone
    model_config = {"from_attributes": True}


class PaginatedIncidents(BaseModel):
    incidents: List[IncidentResponse]
    total: int
    page: int
    per_page: int
    pages: int


class StatsResponse(BaseModel):
    total: int
    unverified: int
    verified: int
    escalated: int
    by_category: List[dict]
    by_state: List[dict]


class HotspotResponse(BaseModel):
    lat: float
    lng: float
    incident_count: int
    state: str
    lga: str
    categories: List[str]
    latest_incident: datetime


class AlertResponse(BaseModel):
    id: str
    alert_type: str
    title: str
    body: str
    state: str
    lga: Optional[str] = None
    severity: Literal["low", "medium", "high", "critical"]
    created_at: datetime
    acknowledged: bool = False
