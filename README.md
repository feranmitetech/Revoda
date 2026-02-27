# Revoda — Election Incident Dashboard
### EiE Nigeria · Civic Intelligence Platform

> *"O God of creation, direct our noble cause."*

---

## What Is Revoda?

Revoda is a civic technology platform that transforms citizen reports and observer data into **verified, actionable election intelligence**. It is not an election management body — it makes election problems impossible to ignore through trusted documentation, transparent verification, structured escalation, and lasting institutional memory.

---

## Project Structure

```
revoda/
├── backend/               # Python FastAPI backend
│   ├── main.py            # API routes + WebSocket
│   ├── models.py          # Pydantic data models
│   ├── auth.py            # JWT partner authentication
│   ├── anonymizer.py      # Reporter identity protection
│   ├── hotspot.py         # PostGIS cluster detection
│   ├── notifier.py        # Email + SMS escalation alerts
│   └── requirements.txt
│
├── database/
│   └── schema.sql         # PostgreSQL + PostGIS schema
│
├── mobile/
│   └── report.html        # PWA citizen report form (works offline)
│
└── docker-compose.yml     # Full local dev stack
```

---

## Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| **Backend API** | Python + FastAPI | Async, fast, type-safe; easy ML integration |
| **Database** | PostgreSQL + PostGIS | Geospatial queries, clustering, 37-state hierarchy |
| **Cache / Realtime** | Redis + WebSockets | Live dashboard feed, hotspot alerts |
| **Frontend Dashboard** | React + TypeScript | Interactive map, real-time state |
| **Map** | Leaflet.js + OpenStreetMap | Free, offline-capable, Nigeria-specific data |
| **Mobile** | PWA (HTML/JS) | Works on Android without app store — critical for Nigeria |
| **SMS Fallback** | Africa's Talking API | Feature phone users can submit via USSD/SMS |
| **Hosting** | AWS + Cloudflare | DDoS protection for election day traffic spikes |
| **Background Jobs** | Celery + Redis | Scheduled hotspot scans, materialized view refresh |

---

## Quick Start (Local Development)

### Prerequisites
- Docker + Docker Compose
- Node.js 18+ (for frontend)

```bash
# 1. Clone and enter
git clone https://github.com/eienigeria/revoda.git
cd revoda

# 2. Copy env file
cp .env.example .env
# Edit .env with your secrets

# 3. Start all services (DB, Redis, API, Celery worker)
docker compose up -d

# 4. API is now live at:
#    http://localhost:8000
#    http://localhost:8000/docs  ← Interactive Swagger UI
```

---

## API Reference

### Public Endpoints (no auth required)

| Method | Endpoint | Description |
|--------|---------|-------------|
| `POST` | `/api/v1/incidents` | Submit incident report |
| `GET` | `/api/v1/incidents` | List incidents (filterable) |
| `GET` | `/api/v1/incidents/{id}` | Get single incident |
| `GET` | `/api/v1/stats` | Live national/state stats |
| `GET` | `/api/v1/hotspots` | Active incident clusters |
| `GET` | `/api/v1/map/heatmap` | Heatmap data points |
| `WS` | `/ws/live` | WebSocket live feed |

### Partner Endpoints (JWT required)

| Method | Endpoint | Description |
|--------|---------|-------------|
| `PATCH` | `/api/v1/incidents/{id}/verify` | Verify / escalate / dismiss |
| `POST` | `/api/v1/partners/report` | Bulk CSO data submission |

---

## Anonymisation Architecture

Reporter privacy is a core guarantee:

```
User submits phone: 08012345678
         ↓
Normalised:         2348012345678
         ↓
HMAC-SHA256 with rotating secret key
         ↓
Stored in DB:       anon:7f3a9c2b1e4d8f6a...  (48-char hash)
         ↓
Original phone:     NEVER STORED
```

The hash allows deduplication (detect if same person files 10 identical reports) without enabling re-identification.

---

## Incident Categories

| Category | Description |
|----------|------------|
| `electoral_officials_arrival` | INEC staff arrival time |
| `material_availability` | BVAS machines, ballot papers, forms |
| `voting_irregularity` | Voter suppression, underage voting, multiple voting |
| `vote_counting` | Ballot box snatching, counting disputes |
| `result_announcement` | Form EC8A not displayed, result manipulation |
| `violence` | Physical attacks, thuggery, intimidation |
| `police_behaviour` | Illegal deployment, voter intimidation by police |
| `results_verification` | Collation irregularities, manipulation |

---

## Election Lifecycle Phases

```
Pre-Election          Election Day           Post-Election
━━━━━━━━━━━━━         ━━━━━━━━━━━━━━         ━━━━━━━━━━━━━━
Early warning         Real-time feed         Evidence archive
Risk briefs           Escalation alerts      Reform reports
Hotspot maps          Media briefings        Audit analysis
```

---

## Partner Integration

CSOs and observer groups can integrate via:

1. **REST API** — Submit incidents programmatically with partner JWT
2. **Webhook** — Receive real-time escalation alerts
3. **Data Export** — Pull verified incidents as CSV/JSON for reports

Contact EiE Nigeria to obtain a partner API token.

---

## Roadmap

- [ ] **v1.0** — Core reporting, map dashboard, partner API
- [ ] **v1.1** — SMS/USSD submission via Africa's Talking
- [ ] **v1.2** — Historical election data import (2019, 2023)
- [ ] **v1.3** — AI-powered pattern detection (anomaly flagging)
- [ ] **v1.4** — Public evidence archive with PDF export
- [ ] **v2.0** — Native Android app (React Native)

---

## Environment Variables

```env
DATABASE_URL=postgresql://revoda:revoda@localhost/revoda
REDIS_URL=redis://localhost:6379
JWT_SECRET_KEY=your-strong-secret-here
ANONYMIZER_SECRET=another-strong-secret
SENDGRID_API_KEY=your-sendgrid-key
AT_USERNAME=your-africas-talking-username
AT_API_KEY=your-africas-talking-key
ALERT_EMAIL_LIST=security@eienigeria.org,alerts@eienigeria.org
ALERT_SMS_NUMBERS=+2348000000000,+2349000000000
```

---

## License

GNU Affero General Public License v3.0 — Open source for civic use.

Built with ❤️ for Nigerian democracy by EiE Nigeria.
