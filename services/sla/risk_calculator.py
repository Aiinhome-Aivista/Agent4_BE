"""
SLA Risk Calculator — Rule-Based Weighted Scoring Engine
Architecture supports future ML model replacement.

Risk Score Components (total weight = 100):
  - Remaining SLA time      : 30
  - Priority                : 20
  - Reassignment count      : 15
  - Incident age            : 15
  - Historical resolution   : 10
  - Team workload proxy     : 10
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List
from database.db_connection import get_db_connection

logger = logging.getLogger(__name__)

# SLA time budgets by priority (hours)
SLA_BUDGET_HOURS = {
    "critical": 4,
    "high":     8,
    "medium":   24,
    "low":      72,
}

# Weight configuration — easy to swap for ML features later
WEIGHTS = {
    "sla_remaining":   30,
    "priority":        20,
    "reassignment":    15,
    "incident_age":    15,
    "historical":      10,
    "workload":        10,
}


class SLARiskCalculator:

    def calculate(self, incident: Dict[str, Any]) -> Dict[str, Any]:
        now = datetime.utcnow()
        reasons: List[str] = []
        actions: List[str] = []
        scores: Dict[str, float] = {}

        priority    = incident.get("priority", "medium")
        created_at  = incident.get("created_at")
        sla_due_at  = incident.get("sla_due_at")
        reassign    = int(incident.get("reassignment_count") or 0)
        assignee    = incident.get("assignee", "Unassigned")
        source      = incident.get("source", "")
        ticket_id   = incident.get("ticket_id", "")

        # ── 1. SLA Remaining (weight 30) ──────────────────────────────────────
        budget_h = SLA_BUDGET_HOURS.get(priority, 24)
        if sla_due_at and isinstance(sla_due_at, datetime):
            remaining_h = (sla_due_at - now).total_seconds() / 3600
        elif created_at and isinstance(created_at, datetime):
            elapsed_h = (now - created_at).total_seconds() / 3600
            remaining_h = budget_h - elapsed_h
        else:
            remaining_h = budget_h / 2  # assume half used

        pct_remaining = max(0, remaining_h / budget_h)
        if pct_remaining <= 0:
            sla_score = 100
            reasons.append("SLA already breached or critically overdue")
            actions.append("Escalate immediately to manager")
        elif pct_remaining < 0.1:
            sla_score = 90
            reasons.append(f"Less than 10% SLA time remaining ({remaining_h:.1f}h left)")
            actions.append("Escalate to L2 / senior engineer immediately")
        elif pct_remaining < 0.25:
            sla_score = 70
            reasons.append(f"Less than 25% SLA time remaining ({remaining_h:.1f}h left)")
            actions.append("Prioritize this ticket immediately")
        elif pct_remaining < 0.5:
            sla_score = 40
            reasons.append(f"Approaching SLA deadline ({remaining_h:.1f}h left)")
        else:
            sla_score = 10
        scores["sla_remaining"] = sla_score

        # ── 2. Priority (weight 20) ───────────────────────────────────────────
        priority_scores = {"critical": 100, "high": 70, "medium": 35, "low": 10}
        p_score = priority_scores.get(priority, 35)
        if priority in ("critical", "high"):
            reasons.append(f"Ticket priority is {priority.upper()}")
        scores["priority"] = p_score

        # ── 3. Reassignment Count (weight 15) ─────────────────────────────────
        if reassign == 0:
            r_score = 0
        elif reassign == 1:
            r_score = 30
        elif reassign == 2:
            r_score = 55
            reasons.append(f"Reassigned {reassign} times — possible ownership confusion")
        else:
            r_score = 80
            reasons.append(f"Reassigned {reassign} times — escalation needed")
            actions.append("Reassign to a senior engineer or team lead")
        scores["reassignment"] = r_score

        # ── 4. Incident Age (weight 15) ───────────────────────────────────────
        if created_at and isinstance(created_at, datetime):
            age_h = (now - created_at).total_seconds() / 3600
            age_pct = min(1.0, age_h / budget_h)
            a_score = age_pct * 100
            if age_pct > 0.8:
                reasons.append(f"Ticket is very old ({age_h:.0f}h since creation)")
                actions.append("Review if ticket is stalled")
        else:
            a_score = 50
        scores["incident_age"] = a_score

        # ── 5. Historical Resolution (weight 10) ──────────────────────────────
        avg_resolution_h = self._get_avg_resolution(source, priority)
        if avg_resolution_h and remaining_h < avg_resolution_h:
            h_score = min(100, (avg_resolution_h / max(remaining_h, 0.1)) * 30)
            reasons.append(
                f"Historical avg resolution ({avg_resolution_h:.1f}h) "
                f"exceeds remaining time ({remaining_h:.1f}h)"
            )
            actions.append("Dedicate additional resources")
        else:
            h_score = 10
        scores["historical"] = h_score

        # ── 6. Team Workload Proxy (weight 10) ────────────────────────────────
        if assignee and assignee != "Unassigned":
            open_count = self._get_assignee_open_count(assignee)
            if open_count > 10:
                w_score = 80
                reasons.append(f"Assignee '{assignee}' has {open_count} open tickets")
                actions.append("Reassign ticket to less-loaded engineer")
            elif open_count > 5:
                w_score = 45
                reasons.append(f"Assignee '{assignee}' is moderately loaded ({open_count} tickets)")
            else:
                w_score = 10
        else:
            w_score = 60
            reasons.append("Ticket is unassigned")
            actions.append("Assign ticket to an available engineer immediately")
        scores["workload"] = w_score

        # ── Weighted final score ──────────────────────────────────────────────
        total = sum(scores[k] * WEIGHTS[k] for k in scores) / 100
        risk_score = round(min(100, total), 2)

        high_threshold   = 70
        medium_threshold = 40

        if risk_score >= high_threshold:
            risk_level = "HIGH"
        elif risk_score >= medium_threshold:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        breach_prob = round(min(100, risk_score * 1.05), 1)

        return {
            "ticket_id":          ticket_id,
            "risk_score":         risk_score,
            "risk_level":         risk_level,
            "breach_probability": f"{breach_prob}%",
            "reasons":            reasons or ["No immediate risk factors detected"],
            "recommended_actions": actions or ["Continue monitoring"],
            "score_components":   scores,
        }

    def _get_avg_resolution(self, source: str, priority: str) -> float | None:
        """Compute average resolution time from historical closed incidents."""
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT AVG(TIMESTAMPDIFF(HOUR, created_at, resolved_at)) AS avg_h
                FROM incidents
                WHERE source = %s AND priority = %s
                  AND resolved_at IS NOT NULL
                  AND created_at IS NOT NULL
                LIMIT 1
            """, (source, priority))
            row = cursor.fetchone()
            cursor.close()
            conn.close()
            if row and row["avg_h"]:
                return float(row["avg_h"])
        except Exception as e:
            logger.warning(f"[SLA] avg resolution fetch failed: {e}")
        return None

    def _get_assignee_open_count(self, assignee: str) -> int:
        """Count open tickets for the given assignee."""
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT COUNT(*) AS cnt FROM incidents
                WHERE assignee = %s
                  AND status NOT IN ('resolved','closed','done')
            """, (assignee,))
            row = cursor.fetchone()
            cursor.close()
            conn.close()
            if row:
                return int(row["cnt"] or 0)
        except Exception as e:
            logger.warning(f"[SLA] assignee count fetch failed: {e}")
        return 0
