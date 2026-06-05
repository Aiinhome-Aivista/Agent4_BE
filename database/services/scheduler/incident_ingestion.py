"""
Incident Ingestion Pipeline
Inserts or updates incidents fetched from connectors.
Avoids duplicates via UNIQUE KEY (source, ticket_id).
"""
import json
import logging
from datetime import datetime
from typing import List, Dict, Any
from database.db_connection import get_db_connection
from services.ai.incident_ai_service import IncidentAIService

logger = logging.getLogger(__name__)


def _dt_or_none(v):
    if isinstance(v, datetime):
        return v
    return None


def ingest_incidents(tickets: List[Dict[str, Any]]) -> Dict[str, int]:
    if not tickets:
        return {"inserted": 0, "updated": 0, "errors": 0}

    conn = get_db_connection()
    cursor = conn.cursor()
    inserted = updated = errors = 0

    for t in tickets:
        try:
            raw = t.get("raw_data")
            raw_json = json.dumps(raw, default=str) if raw else None

            cursor.execute("""
                INSERT INTO incidents
                    (source, ticket_id, title, description, priority, status,
                     assignee, reporter, created_at, updated_at, resolved_at,
                     sla_due_at, reassignment_count, raw_data)
                VALUES
                    (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE
                    title               = VALUES(title),
                    description         = VALUES(description),
                    priority            = VALUES(priority),
                    status              = VALUES(status),
                    assignee            = VALUES(assignee),
                    reporter            = VALUES(reporter),
                    updated_at          = VALUES(updated_at),
                    resolved_at         = VALUES(resolved_at),
                    sla_due_at          = VALUES(sla_due_at),
                    reassignment_count  = VALUES(reassignment_count),
                    raw_data            = VALUES(raw_data)
            """, (
                t.get("source"),
                t.get("ticket_id"),
                t.get("title"),
                t.get("description"),
                t.get("priority", "medium"),
                t.get("status", "open"),
                t.get("assignee"),
                t.get("reporter"),
                _dt_or_none(t.get("created_at")),
                _dt_or_none(t.get("updated_at")),
                _dt_or_none(t.get("resolved_at")),
                _dt_or_none(t.get("sla_due_at")),
                t.get("reassignment_count", 0),
                raw_json,
            ))
            if cursor.rowcount == 1:
                inserted += 1
            else:
                updated += 1

            # AI Processing
            IncidentAIService.process_incident(t)
        except Exception as e:
            logger.error(f"[Ingestion] Error for {t.get('ticket_id')}: {e}")
            errors += 1

    conn.commit()
    cursor.close()
    conn.close()
    logger.info(f"[Ingestion] inserted={inserted}, updated={updated}, errors={errors}")
    return {"inserted": inserted, "updated": updated, "errors": errors}
