"""
Scheduler Manager
─────────────────
Two separate intervals (configurable from .env):

  SYNC_INTERVAL_SECONDS   — fetch new/updated tickets from connectors
  SCHEDULER_INTERVAL_SECONDS — run risk scoring + alerting loop

Both survive backend restart. Active connectors are loaded from DB on startup.
"""
import os
import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger


logger = logging.getLogger(__name__)

SYNC_INTERVAL     = int(os.getenv("SYNC_INTERVAL_SECONDS", 60))
SCHEDULER_INTERVAL = int(os.getenv("SCHEDULER_INTERVAL_SECONDS", 120))

_scheduler = BackgroundScheduler(timezone="UTC")


# ── Job 1: Ticket sync ────────────────────────────────────────────────────────
def _sync_tickets_job():
    """Fetch NEW/UPDATED tickets from all active connectors and ingest them."""
    from database.db_connection import get_db_connection
    from services.connectors.jira_connector import JiraConnector
    from services.connectors.servicenow_connector import ServiceNowConnector
    from services.scheduler.incident_ingestion import ingest_incidents

    CONNECTOR_MAP = {"jira": JiraConnector, "servicenow": ServiceNowConnector}

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT id, connector_type, base_url, username, api_token, app_id, last_synced_at
            FROM connector_configs
            WHERE is_active = 1
        """)
        configs = cursor.fetchall()
        cursor.close()
        conn.close()
    except Exception as e:
        logger.error(f"[Scheduler] Failed to load connector configs: {e}")
        return

    for cfg in configs:
        ctype = cfg["connector_type"]
        cls = CONNECTOR_MAP.get(ctype)
        if not cls:
            continue

        since = cfg.get("last_synced_at")  # datetime or None
        svc = cls(cfg["base_url"], cfg["username"], cfg["api_token"], cfg.get("app_id"))
        logger.info(f"[Sync] Fetching {ctype} tickets since {since} (project: {cfg.get('app_id')})")

        try:
            tickets = svc.fetch_tickets(since=since)
            result = ingest_incidents(tickets)
            logger.info(f"[Sync] {ctype} → {result}")

            # Update last_synced_at
            conn2 = get_db_connection()
            cur2 = conn2.cursor()
            cur2.execute(
                "UPDATE connector_configs SET last_synced_at = %s WHERE id = %s",
                (datetime.utcnow(), cfg["id"])
            )
            conn2.commit()
            cur2.close()
            conn2.close()
        except Exception as e:
            logger.error(f"[Sync] Error syncing {ctype}: {e}")


# ── Job 2: Risk scoring + alerts ──────────────────────────────────────────────
def _risk_and_alert_job():
    """Calculate risk scores for all open incidents and send alerts."""
    from services.sla.risk_scoring_job import run_risk_scoring
    from services.alerts.alert_service import send_high_risk_alerts

    logger.info("[Scheduler] Running risk scoring...")
    try:
        high_risk = run_risk_scoring()
        if high_risk:
            logger.info(f"[Scheduler] {len(high_risk)} HIGH risk incidents — sending alerts")
            send_high_risk_alerts(high_risk)
    except Exception as e:
        logger.error(f"[Scheduler] Risk scoring error: {e}")


# ── Public API ────────────────────────────────────────────────────────────────
def start_scheduler():
    if _scheduler.running:
        logger.info("[Scheduler] Already running.")
        return

    _scheduler.add_job(
        _sync_tickets_job,
        trigger=IntervalTrigger(seconds=SYNC_INTERVAL),
        id="sync_tickets",
        replace_existing=True,
        misfire_grace_time=30,
    )

    _scheduler.add_job(
        _risk_and_alert_job,
        trigger=IntervalTrigger(seconds=SCHEDULER_INTERVAL),
        id="risk_and_alert",
        replace_existing=True,
        misfire_grace_time=30,
    )

    _scheduler.start()
    logger.info(
        f"[Scheduler] Started — "
        f"sync every {SYNC_INTERVAL}s, risk/alert every {SCHEDULER_INTERVAL}s"
    )


def stop_scheduler():
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("[Scheduler] Stopped.")


def get_scheduler_status() -> dict:
    jobs = []
    for job in _scheduler.get_jobs():
        next_run = job.next_run_time
        jobs.append({
            "id": job.id,
            "next_run": next_run.isoformat() if next_run else None,
        })
    return {
        "running": _scheduler.running,
        "sync_interval_seconds": SYNC_INTERVAL,
        "scheduler_interval_seconds": SCHEDULER_INTERVAL,
        "jobs": jobs,
    }
