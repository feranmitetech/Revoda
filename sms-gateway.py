"""
Revoda — SMS & USSD Gateway
Allows feature phone users to submit incident reports via SMS/USSD.
Critical for Nigeria where many voters don't have smartphones.

Integrates with Africa's Talking API (Nigerian shortcode).
USSD shortcode: *384*REVODA# (register with NCC)
SMS shortcode: 32144

Flow:
  1. User dials *384# or sends SMS to 32144
  2. USSD menu guides through category + location
  3. Report is parsed and submitted to main API
  4. Confirmation SMS sent back

SMS format: REVODA [CATEGORY_CODE] [STATE] [DESCRIPTION]
  Example: REVODA VIO RIVERS Thugs at PU 007 Obio-Akpor
"""

from fastapi import APIRouter, Form, Request
from fastapi.responses import PlainTextResponse
import httpx
import re
from enum import Enum

router = APIRouter(prefix="/sms", tags=["SMS/USSD Gateway"])

API_BASE = "http://localhost:8000/api/v1"

# Category short codes for SMS
SMS_CATEGORY_CODES = {
    "VIO": "violence",
    "VOT": "voting_irregularity",
    "MAT": "material_availability",
    "POL": "police_behaviour",
    "CNT": "vote_counting",
    "RES": "results_verification",
    "OFF": "electoral_officials_arrival",
    "ANN": "result_announcement",
}

# USSD session storage (use Redis in production)
_ussd_sessions: dict = {}


# ── SMS ENDPOINT ──────────────────────────────────────────────────────────────

@router.post("/incoming", response_class=PlainTextResponse)
async def receive_sms(
    from_: str = Form(alias="from"),
    to: str = Form(),
    text: str = Form(),
    date: str = Form(default=""),
    id: str = Form(default=""),
):
    """
    Receives incoming SMS from Africa's Talking.
    Expected format: REVODA VIO RIVERS Description of what happened
    """
    text = text.strip().upper()

    if not text.startswith("REVODA"):
        return "Welcome to Revoda. To report an incident, text: REVODA [CODE] [STATE] [DESCRIPTION]\nCodes: VIO=Violence VOT=Voting MAT=Materials POL=Police CNT=Counting RES=Results"

    parts = text.split(None, 3)  # ["REVODA", "CODE", "STATE", "description"]

    if len(parts) < 4:
        return (
            "Invalid format. Use: REVODA [CODE] [STATE] [DESCRIPTION]\n"
            "Codes: VIO VOT MAT POL CNT RES OFF ANN\n"
            "Example: REVODA VIO RIVERS Thugs at polling unit 007"
        )

    _, code, state_raw, description = parts
    category = SMS_CATEGORY_CODES.get(code)

    if not category:
        return f"Unknown code '{code}'. Valid codes: " + " ".join(SMS_CATEGORY_CODES.keys())

    # Normalise state
    state = _match_state(state_raw.title())
    if not state:
        return f"State '{state_raw}' not recognised. Please use full state name (e.g. LAGOS, RIVERS, KANO)"

    # Submit to API (anonymised — phone is hashed server-side)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(f"{API_BASE}/incidents", json={
                "category": category,
                "description": description.strip().capitalize(),
                "state": state,
                "reporter_type": "citizen",
                "reporter_phone": from_,  # hashed server-side, never stored raw
            })
            if resp.status_code == 201:
                data = resp.json()
                ref_id = str(data.get("id", ""))[:8].upper()
                return (
                    f"✓ Report received. Ref: RVD-{ref_id}\n"
                    f"Category: {code} | State: {state}\n"
                    "Your identity is protected. Thank you for your civic duty."
                )
            else:
                return "Error submitting report. Please try again or call EiE Nigeria: 09012345678"
    except Exception as e:
        return "Service temporarily unavailable. Please try again in a few minutes."


# ── USSD ENDPOINT ──────────────────────────────────────────────────────────────

@router.post("/ussd", response_class=PlainTextResponse)
async def handle_ussd(
    sessionId: str = Form(),
    serviceCode: str = Form(),
    phoneNumber: str = Form(),
    text: str = Form(default=""),
):
    """
    USSD menu flow for Africa's Talking.
    Returns CON (continue session) or END (terminate session).
    """
    session = _ussd_sessions.setdefault(sessionId, {})
    inputs = [t.strip() for t in text.split("*") if t.strip()] if text else []

    # Step 0: Main menu
    if not inputs:
        return "CON Welcome to REVODA\nReport election incidents anonymously\n\n1. Report Incident\n2. Check Report Status\n3. Help"

    # Branch: Help
    if inputs[0] == "3":
        return "END REVODA is run by EiE Nigeria.\nYour identity is fully protected.\nSMS: REVODA [CODE] [STATE] [description] to 32144\nCall: 09012345678"

    # Branch: Status check
    if inputs[0] == "2":
        if len(inputs) < 2:
            return "CON Enter your Report ID (e.g. RVD-ABC123):"
        ref = inputs[1].strip().upper()
        return f"END Checking status of {ref}...\nPlease visit revoda.eienigeria.org or call EiE Nigeria for status updates."

    # Branch: Report incident (inputs[0] == "1")
    if inputs[0] != "1":
        return "END Invalid option. Please try again."

    # Step 1: Category
    if len(inputs) == 1:
        return (
            "CON Select incident type:\n"
            "1. Violence / Thuggery\n"
            "2. Voting Irregularity\n"
            "3. Materials / Equipment\n"
            "4. Police Behaviour\n"
            "5. Vote Counting\n"
            "6. Results Issues"
        )

    cat_map = {
        "1":"violence","2":"voting_irregularity","3":"material_availability",
        "4":"police_behaviour","5":"vote_counting","6":"results_verification"
    }
    category = cat_map.get(inputs[1])
    if not category:
        return "END Invalid selection. Please try again."

    # Step 2: State
    if len(inputs) == 2:
        session["category"] = category
        return (
            "CON Enter your state number:\n"
            "1.Lagos 2.Rivers 3.Kano 4.FCT 5.Imo\n"
            "6.Delta 7.Kaduna 8.Oyo 9.Borno 10.Other"
        )

    quick_states = {
        "1":"Lagos","2":"Rivers","3":"Kano","4":"FCT","5":"Imo",
        "6":"Delta","7":"Kaduna","8":"Oyo","9":"Borno","10":"Other"
    }
    state_choice = quick_states.get(inputs[2], "Other")

    if state_choice == "Other":
        if len(inputs) == 3:
            return "CON Type your state name:"
        state = inputs[3].title() if len(inputs) > 3 else "Other"
    else:
        state = state_choice

    session["state"] = state

    # Step 3: Brief description
    if len(inputs) <= (4 if state_choice == "Other" else 3):
        return "CON Briefly describe the incident\n(e.g. 'Thugs stopped voting at PU 7'):"

    desc_idx = 5 if state_choice == "Other" else 4
    if len(inputs) < desc_idx:
        return "CON Briefly describe the incident:"

    description = inputs[desc_idx - 1] if len(inputs) >= desc_idx else "Incident reported via USSD"

    # Submit
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(f"{API_BASE}/incidents", json={
                "category": session.get("category", category),
                "description": description,
                "state": session.get("state", state),
                "reporter_type": "citizen",
                "reporter_phone": phoneNumber,
            })
            if resp.status_code == 201:
                data = resp.json()
                ref_id = str(data.get("id",""))[:8].upper()
                _ussd_sessions.pop(sessionId, None)
                return f"END Report submitted!\nRef: RVD-{ref_id}\nThank you for protecting Nigeria's democracy. Your identity is protected."
            else:
                return "END Error submitting. Please SMS: REVODA [details] to 32144"
    except Exception:
        return "END Service unavailable. Please SMS: REVODA [details] to 32144"


# ── HELPERS ────────────────────────────────────────────────────────────────────

STATES = [
    "Abia","Adamawa","Akwa Ibom","Anambra","Bauchi","Bayelsa","Benue","Borno",
    "Cross River","Delta","Ebonyi","Edo","Ekiti","Enugu","FCT","Gombe","Imo",
    "Jigawa","Kaduna","Kano","Katsina","Kebbi","Kogi","Kwara","Lagos",
    "Nasarawa","Niger","Ogun","Ondo","Osun","Oyo","Plateau","Rivers",
    "Sokoto","Taraba","Yobe","Zamfara"
]

def _match_state(raw: str) -> str | None:
    raw = raw.strip().title()
    # Exact match
    if raw in STATES:
        return raw
    # Partial match (e.g. "FCT" → "FCT", "Riv" → "Rivers")
    for s in STATES:
        if s.upper().startswith(raw.upper()) or raw.upper() in s.upper():
            return s
    return None
