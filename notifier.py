"""
Revoda — Escalation Alert Notifier
Sends alerts via Email + SMS when incidents are escalated.
"""

import os
import httpx
from typing import Optional


SENDGRID_KEY = os.getenv("SENDGRID_API_KEY", "")
ALERT_FROM_EMAIL = "alerts@revoda.eienigeria.org"
ALERT_RECIPIENTS = os.getenv("ALERT_EMAIL_LIST", "").split(",")

AT_USERNAME = os.getenv("AT_USERNAME", "")
AT_API_KEY = os.getenv("AT_API_KEY", "")
ALERT_SMS_NUMBERS = os.getenv("ALERT_SMS_NUMBERS", "").split(",")


async def send_escalation_alert(incident: dict, partner: dict):
    """Fire email + SMS alert when an incident is escalated."""
    subject = f"[REVODA ESCALATION] {incident['category'].upper()} — {incident['lga']}, {incident['state']}"
    body = f"""
ESCALATED INCIDENT REPORT
==========================
ID:          {incident['id']}
Category:    {incident['category']}
Location:    {incident.get('lga', '')}, {incident['state']}
PU Code:     {incident.get('polling_unit_code', 'N/A')}
Status:      ESCALATED
Escalated by: {partner['org_name']}
Notes:       {incident.get('verification_notes', 'None')}

Description:
{incident['description']}

View on dashboard: https://revoda.eienigeria.org/incident/{incident['id']}
"""

    await _send_email(subject, body)
    await _send_sms(f"[REVODA] ESCALATED: {incident['category']} in {incident.get('lga','')}, {incident['state']}. ID: {str(incident['id'])[:8].upper()}")


async def _send_email(subject: str, body: str):
    if not SENDGRID_KEY:
        print(f"[EMAIL MOCK] {subject}")
        return
    async with httpx.AsyncClient() as client:
        await client.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={"Authorization": f"Bearer {SENDGRID_KEY}"},
            json={
                "personalizations": [{"to": [{"email": e} for e in ALERT_RECIPIENTS if e]}],
                "from": {"email": ALERT_FROM_EMAIL},
                "subject": subject,
                "content": [{"type": "text/plain", "value": body}]
            }
        )


async def _send_sms(message: str):
    if not AT_API_KEY:
        print(f"[SMS MOCK] {message}")
        return
    import africastalking
    africastalking.initialize(AT_USERNAME, AT_API_KEY)
    sms = africastalking.SMS
    sms.send(message, ALERT_SMS_NUMBERS)
