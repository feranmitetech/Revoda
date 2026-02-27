# Revoda — Go-Live Runbook & Deployment Guide
## EiE Nigeria · Election Incident Dashboard

---

## 🚀 Complete Go-Live Checklist

### PHASE 1 — Infrastructure Setup (Week 1)

#### Server Setup
- [ ] Provision Ubuntu 22.04 LTS VPS (minimum: 4 vCPU, 8GB RAM, 100GB SSD)
  - Recommended: AWS EC2 `t3.xlarge` (Nigeria region: af-south-1 Cape Town, or eu-west-1)
  - Alternatively: DigitalOcean Droplet or Render.com
- [ ] Point domain `revoda.eienigeria.org` to server IP (DNS A record)
- [ ] Point `api.revoda.eienigeria.org` to same server
- [ ] Install Docker + Docker Compose
  ```bash
  curl -fsSL https://get.docker.com | sh
  sudo usermod -aG docker $USER
  ```
- [ ] Install Nginx
  ```bash
  sudo apt install nginx certbot python3-certbot-nginx
  ```
- [ ] Get SSL certificate
  ```bash
  sudo certbot --nginx -d revoda.eienigeria.org -d api.revoda.eienigeria.org
  ```
- [ ] Set up Cloudflare in front of server (free tier) — DDoS protection critical on election day

#### Database
- [ ] Run schema.sql on production PostgreSQL
  ```bash
  docker compose up -d db
  docker compose exec db psql -U revoda -d revoda -f /schema.sql
  ```
- [ ] Import Nigeria polling unit data (get from INEC portal)
- [ ] Import historical incident data from 2019, 2023 elections

---

### PHASE 2 — Application Deployment (Week 1-2)

#### Backend API
- [ ] Copy `.env.example` to `.env` and fill ALL values:
  ```
  DATABASE_URL=postgresql://revoda:[PASSWORD]@db/revoda
  REDIS_URL=redis://redis:6379
  JWT_SECRET_KEY=[generate: openssl rand -hex 32]
  ANONYMIZER_SECRET=[generate: openssl rand -hex 32]
  SENDGRID_API_KEY=[from sendgrid.com]
  AT_USERNAME=[from africastalking.com]
  AT_API_KEY=[from africastalking.com]
  ALERT_EMAIL_LIST=security@eienigeria.org,director@eienigeria.org
  ALERT_SMS_NUMBERS=+2348XXXXXXXXX,+2349XXXXXXXXX
  ```
- [ ] Start all services
  ```bash
  docker compose up -d
  docker compose ps  # verify all healthy
  ```
- [ ] Test API health: `curl https://api.revoda.eienigeria.org/api/v1/stats`

#### Frontend
- [ ] Build React app
  ```bash
  cd frontend && npm ci && npm run build
  ```
- [ ] Copy `dist/` to `/var/www/revoda/dashboard/dist/`
- [ ] Copy `mobile/report.html` to `/var/www/revoda/mobile/`
- [ ] Copy `admin/index.html` to `/var/www/revoda/admin/`
- [ ] Apply nginx config from `deployment/nginx.conf`
  ```bash
  sudo cp deployment/nginx.conf /etc/nginx/sites-available/revoda
  sudo ln -s /etc/nginx/sites-available/revoda /etc/nginx/sites-enabled/
  sudo nginx -t && sudo systemctl reload nginx
  ```

#### CI/CD
- [ ] Push code to GitHub repo `eienigeria/revoda`
- [ ] Add GitHub Secrets:
  - `PROD_HOST` = server IP
  - `PROD_USER` = deploy user
  - `PROD_SSH_KEY` = SSH private key
  - `SLACK_WEBHOOK` = Slack notifications
- [ ] Test pipeline with a dummy push

---

### PHASE 3 — Integrations (Week 2)

#### Africa's Talking (SMS/USSD)
- [ ] Register at africastalking.com
- [ ] Apply for Nigerian shortcode (can take 2-4 weeks — start EARLY)
  - SMS: Apply for 5-digit shortcode (e.g. 32144)
  - USSD: Apply for *384*CODE# (coordinate with NCC)
- [ ] Configure webhook URL: `https://revoda.eienigeria.org/sms/incoming`
- [ ] Configure USSD callback: `https://revoda.eienigeria.org/sms/ussd`
- [ ] Test SMS: Send "REVODA VIO RIVERS Test incident" to shortcode
- [ ] Test USSD: Dial the shortcode on a test SIM

#### SendGrid (Email Alerts)
- [ ] Create account at sendgrid.com
- [ ] Verify sender domain `revoda.eienigeria.org`
- [ ] Create API key with "Mail Send" permission
- [ ] Test: Trigger a test escalation alert
- [ ] Set up dedicated IP (for production sending reputation)

#### Partner Onboarding
- [ ] Generate API tokens for each partner:
  ```bash
  docker compose exec api python -c "from auth import create_partner_token; print(create_partner_token('YIAGA Africa', {'submit':True,'verify':True,'escalate':False}))"
  ```
- [ ] Document tokens securely and distribute to partner tech teams
- [ ] Run integration test with each partner's system
- [ ] Brief partner staff on verification workflow

---

### PHASE 4 — Security & Testing (Week 2-3)

- [ ] Run penetration test (focus: API auth bypass, SQL injection, XSS)
- [ ] Verify anonymisation: confirm no raw phone numbers in DB
  ```sql
  SELECT reporter_anon_hash, reporter_phone FROM incidents LIMIT 10;
  -- reporter_phone should be NULL on all rows
  ```
- [ ] Load test API with Locust: simulate election day traffic (10,000 concurrent users)
  ```bash
  pip install locust
  locust -f tests/locustfile.py --host=https://api.revoda.eienigeria.org
  ```
- [ ] Test offline mode: disconnect mobile device, submit report, reconnect
- [ ] Test WebSocket auto-reconnect
- [ ] Verify admin panel restricted to whitelisted IPs
- [ ] Configure automated backups:
  ```bash
  # Add to crontab: pg_dump every 6 hours
  0 */6 * * * docker compose exec db pg_dump -U revoda revoda | gzip > /backups/revoda-$(date +%Y%m%d%H%M).sql.gz
  ```

---

### PHASE 5 — Election Day Preparation

- [ ] Switch election phase to `election_day` in DB:
  ```sql
  UPDATE elections SET phase = 'election_day' WHERE is_active = TRUE;
  ```
- [ ] Scale up server (election day: 8 vCPU, 16GB RAM minimum)
- [ ] Brief EiE Nigeria admin team on verification console
- [ ] Set up dedicated monitoring: uptime.betterstack.com or similar
- [ ] Confirm Cloudflare DDoS protection is active
- [ ] Pre-position verification volunteers in each geopolitical zone
- [ ] Set up war room comms channel (WhatsApp/Slack)
- [ ] Test all emergency contacts reachable via SMS

---

## 📞 Emergency Contacts (Fill in before go-live)

| Role | Name | Phone | Email |
|------|------|-------|-------|
| Tech Lead | | | |
| Server Admin | | | |
| EiE Nigeria Director | | | |
| Cloudflare Emergency | +1-650-319-8930 | | |
| Africa's Talking Support | | | support@africastalking.com |

---

## 🗂️ File Locations on Production Server

```
/opt/revoda/                  ← Docker Compose + .env
/var/www/revoda/
  dashboard/dist/             ← React build
  mobile/report.html          ← Citizen PWA
  admin/index.html            ← Partner console
/etc/nginx/sites-available/revoda
/var/log/revoda/              ← Application logs
/backups/                     ← Database dumps
```

---

## Quick Commands

```bash
# View live logs
docker compose logs -f api

# Restart API only
docker compose restart api

# Check DB connection count
docker compose exec db psql -U revoda -c "SELECT count(*) FROM pg_stat_activity;"

# Emergency: flush Redis cache
docker compose exec redis redis-cli FLUSHALL

# Database backup now
docker compose exec db pg_dump -U revoda revoda > backup-$(date +%Y%m%d).sql

# Generate new partner token
docker compose exec api python -c "
from auth import create_partner_token
token = create_partner_token('Partner Name', {'submit':True,'verify':True,'escalate':False})
print(token)
"
```

---

*Built for EiE Nigeria — Protecting Nigerian Democracy*
*revoda.eienigeria.org*
