"""
Alert service — sends SLA breach warning emails.
Sends to: all users with role='engineer'.
"""
import os
import json
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Any
from database.db_connection import get_db_connection

logger = logging.getLogger(__name__)

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
FROM_EMAIL = os.getenv("ALERT_FROM_EMAIL", SMTP_USER)


def _get_engineer_emails() -> List[str]:
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT email FROM users WHERE role = 'engineer'")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return [r["email"] for r in rows]


def _send_email(to_emails: List[str], subject: str, html_body: str):
    if not SMTP_USER or not SMTP_PASSWORD:
        logger.warning("[Alert] SMTP not configured — skipping email send")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = FROM_EMAIL
    msg["To"] = ", ".join(to_emails)
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(FROM_EMAIL, to_emails, msg.as_string())
        logger.info(f"[Alert] Email sent to {to_emails}")
    except Exception as e:
        logger.error(f"[Alert] Email send failed: {e}")


def _build_email_body(incidents: List[Dict[str, Any]]) -> str:
    rows = ""
    for inc in incidents:
        reasons = inc.get("reasons", [])
        actions = inc.get("recommended_actions", [])
        rows += f"""
        <tr>
          <td style="padding:8px;border:1px solid #e2e8f0">{inc.get('ticket_id','')}</td>
          <td style="padding:8px;border:1px solid #e2e8f0">{inc.get('title','')[:80]}</td>
          <td style="padding:8px;border:1px solid #e2e8f0;color:#dc2626;font-weight:bold">
            {inc.get('risk_score','')} ({inc.get('risk_level','')})
          </td>
          <td style="padding:8px;border:1px solid #e2e8f0">{inc.get('breach_probability','')}</td>
          <td style="padding:8px;border:1px solid #e2e8f0">{'<br>'.join(reasons[:2])}</td>
          <td style="padding:8px;border:1px solid #e2e8f0">{'<br>'.join(actions[:2])}</td>
        </tr>
        """

    return f"""
    <html><body style="font-family:Arial,sans-serif;color:#1e293b">
    <h2 style="color:#dc2626">⚠️ SLA Breach Alert — High Risk Incidents Detected</h2>
    <p>The following incidents are at HIGH risk of breaching SLA and require immediate attention:</p>
    <table style="border-collapse:collapse;width:100%;font-size:13px">
      <thead>
        <tr style="background:#f1f5f9">
          <th style="padding:8px;border:1px solid #e2e8f0">Ticket ID</th>
          <th style="padding:8px;border:1px solid #e2e8f0">Title</th>
          <th style="padding:8px;border:1px solid #e2e8f0">Risk Score</th>
          <th style="padding:8px;border:1px solid #e2e8f0">Breach Probability</th>
          <th style="padding:8px;border:1px solid #e2e8f0">Reasons</th>
          <th style="padding:8px;border:1px solid #e2e8f0">Recommended Actions</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>
    <p style="color:#64748b;font-size:12px;margin-top:20px">
      — SLA Risk Engine | Automated Alert
    </p>
    </body></html>
    """


def _log_alert(incident_id: int, sent_to: List[str], message: str):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO alert_log (incident_id, alert_type, message, sent_to)
            VALUES (%s, 'SLA_BREACH_RISK', %s, %s)
        """, (incident_id, message, json.dumps(sent_to)))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        logger.warning(f"[Alert] Failed to log alert: {e}")


def send_high_risk_alerts(high_risk_incidents: List[Dict[str, Any]]):
    if not high_risk_incidents:
        return

    to_emails = _get_engineer_emails()
    if not to_emails:
        logger.warning("[Alert] No engineers found to alert")
        return

    body = _build_email_body(high_risk_incidents)
    subject = f"⚠️ SLA Risk Alert — {len(high_risk_incidents)} HIGH risk incident(s) require attention"
    _send_email(to_emails, subject, body)

    for inc in high_risk_incidents:
        inc_id = inc.get("id")
        if inc_id:
            _log_alert(inc_id, to_emails, f"High risk alert sent for {inc.get('ticket_id')}")
