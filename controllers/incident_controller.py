from database.db_connection import get_db_connection

def fetch_all_incidents(
    page: int = 1,
    per_page: int = 20,
    risk_level: str = "",
    source: str = ""
):
    offset = (page - 1) * per_page

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    where_clauses = []
    params = []

    if risk_level:
        where_clauses.append("s.risk_level = %s")
        params.append(risk_level.upper())

    if source:
        where_clauses.append("i.source = %s")
        params.append(source.lower())

    where_sql = (
        "WHERE " + " AND ".join(where_clauses)
        if where_clauses
        else ""
    )

    cursor.execute(f"""
        SELECT 
            i.*,

            s.risk_score,
            s.risk_level,
            s.breach_probability,
            s.reasons,
            s.recommended_actions,
            s.calculated_at,

            ai.summary,
            ai.solution,
            ai.impact_score,
            ai.urgency_score,
            ai.complexity_score,
            ai.sla_breach_score,
            ai.new_ticket_score,
            ai.risk_score AS ai_risk_score,
            ai.estimated_resolution_time

        FROM incidents i

        LEFT JOIN sla_risk_scores s 
            ON s.incident_id = i.id
            AND s.id = (
                SELECT MAX(id)
                FROM sla_risk_scores
                WHERE incident_id = i.id
            )

        LEFT JOIN incident_ai_analysis ai
            ON ai.incident_id = i.id
            AND ai.id = (
                SELECT MAX(id)
                FROM incident_ai_analysis
                WHERE incident_id = i.id
            )

        {where_sql}

        ORDER BY s.risk_score DESC, i.updated_at DESC
        LIMIT %s OFFSET %s
    """, params + [per_page, offset])

    rows = cursor.fetchall()

    cursor.execute(f"""
        SELECT COUNT(*) AS total

        FROM incidents i

        LEFT JOIN sla_risk_scores s 
            ON s.incident_id = i.id
            AND s.id = (
                SELECT MAX(id)
                FROM sla_risk_scores
                WHERE incident_id = i.id
            )

        LEFT JOIN incident_ai_analysis ai
            ON ai.incident_id = i.id
            AND ai.id = (
                SELECT MAX(id)
                FROM incident_ai_analysis
                WHERE incident_id = i.id
            )

        {where_sql}
    """, params)

    total = cursor.fetchone()["total"]

    cursor.close()
    conn.close()

    for row in rows:
        for k in [
            "created_at",
            "updated_at",
            "resolved_at",
            "sla_due_at",
            "ingested_at",
            "calculated_at",
        ]:
            if row.get(k):
                row[k] = row[k].isoformat()

        # Ensure AI component scores are always present (avoid nulls in UI).
        row["impact_score"] = row.get("impact_score") or 0
        row["urgency_score"] = row.get("urgency_score") or 0
        row["complexity_score"] = row.get("complexity_score") or 0
        row["sla_breach_score"] = row.get("sla_breach_score") or 0
        row["new_ticket_score"] = row.get("new_ticket_score") or 0

        # Ensure ai_risk_score is always present.
        row["ai_risk_score"] = row.get("ai_risk_score") or 0

    return {
        "incidents": rows,
        "total": total,
        "page": page,
        "per_page": per_page
    }
def fetch_incident_by_id(incident_id: int):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT 
            i.id,
            i.ticket_id,
            i.title,
            i.description,
            i.source,
            i.status,
            i.priority,
            i.assignee,
            i.created_at,
            i.updated_at,
            i.resolved_at,
            i.sla_due_at,
            i.ingested_at,

            s.risk_score AS sla_risk_score,
            s.risk_level,
            s.breach_probability,
            s.reasons,
            s.recommended_actions,
            s.calculated_at,

            ai.summary AS ai_summary,
            ai.solution AS ai_solution,
            ai.impact_score,
            ai.urgency_score,
            ai.complexity_score,
            ai.sla_breach_score,
            ai.new_ticket_score,
            ai.risk_score AS ai_risk_score,
            ai.estimated_resolution_time

        FROM incidents i

        LEFT JOIN sla_risk_scores s 
            ON s.incident_id = i.id
            AND s.id = (
                SELECT MAX(id)
                FROM sla_risk_scores
                WHERE incident_id = i.id
            )

        LEFT JOIN incident_ai_analysis ai
            ON ai.incident_id = i.id
            AND ai.id = (
                SELECT MAX(id)
                FROM incident_ai_analysis
                WHERE incident_id = i.id
            )

        WHERE i.id = %s
        LIMIT 1
    """, (incident_id,))

    row = cursor.fetchone()

    cursor.close()
    conn.close()

    if not row:
        return None

    for key in [
        "created_at",
        "updated_at",
        "resolved_at",
        "sla_due_at",
        "ingested_at",
        "calculated_at"
    ]:
        if row.get(key):
            row[key] = row[key].isoformat()

    return {
        "id": row.get("id"),
        "title": row.get("title"),
        "description": row.get("description"),
        "source": row.get("source"),
        "status": row.get("status"),
        "priority": row.get("priority"),

        "ai_summary": row.get("ai_summary", ""),
        "ai_solution": row.get("ai_solution", ""),

        "impact_score": row.get("impact_score", 0),
        "urgency_score": row.get("urgency_score", 0),
        "complexity_score": row.get("complexity_score", 0),
        "sla_breach_score": row.get("sla_breach_score", 0),
        "new_ticket_score": row.get("new_ticket_score", 0),

        "risk_score": row.get("ai_risk_score", 0),
        "estimated_resolution_time": row.get("estimated_resolution_time", "")
    }

def fetch_dashboard_metrics():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            COUNT(*) AS total_incidents,

            SUM(CASE WHEN s.risk_level='HIGH'   THEN 1 ELSE 0 END) AS high_risk,
            SUM(CASE WHEN s.risk_level='MEDIUM' THEN 1 ELSE 0 END) AS medium_risk,
            SUM(CASE WHEN s.risk_level='LOW'    THEN 1 ELSE 0 END) AS low_risk,

            AVG(s.risk_score) AS avg_risk_score,
            AVG(ai.risk_score) AS ai_risk_score

        FROM incidents i

        LEFT JOIN sla_risk_scores s
            ON s.incident_id = i.id
            AND s.id = (
                SELECT MAX(id)
                FROM sla_risk_scores
                WHERE incident_id = i.id
            )

        LEFT JOIN incident_ai_analysis ai
            ON ai.incident_id = i.id
            AND ai.id = (
                SELECT MAX(id)
                FROM incident_ai_analysis
                WHERE incident_id = i.id
            )

        WHERE i.status NOT IN ('resolved','closed','done')
    """)

    stats = cursor.fetchone()

    # Convert Decimals for JSON serialization
    if stats:
        for k, v in stats.items():
            if v is not None:
                stats[k] = float(v) if hasattr(v, '__float__') else v

    cursor.execute("""
        SELECT source, COUNT(*) AS count
        FROM incidents
        WHERE status NOT IN ('resolved','closed','done')
        GROUP BY source
    """)
    by_source = cursor.fetchall()

    cursor.execute("""
        SELECT priority, COUNT(*) AS count
        FROM incidents
        WHERE status NOT IN ('resolved','closed','done')
        GROUP BY priority
    """)
    by_priority = cursor.fetchall()

    cursor.execute("""
        SELECT
            i.id,
            i.ticket_id,
            i.title,
            i.source,
            i.priority,

            s.risk_score,
            s.risk_level,
            s.breach_probability,

            ai.risk_score AS ai_risk_score

        FROM incidents i

        JOIN sla_risk_scores s
            ON s.incident_id = i.id
            AND s.id = (
                SELECT MAX(id)
                FROM sla_risk_scores
                WHERE incident_id = i.id
            )

        LEFT JOIN incident_ai_analysis ai
            ON ai.incident_id = i.id
            AND ai.id = (
                SELECT MAX(id)
                FROM incident_ai_analysis
                WHERE incident_id = i.id
            )

        WHERE i.status NOT IN ('resolved','closed','done')

        ORDER BY s.risk_score DESC
        LIMIT 5
    """)

    top_risk = cursor.fetchall()

    cursor.close()
    conn.close()

    return {
        "stats": stats,
        "by_source": by_source,
        "by_priority": by_priority,
        "top_risk_incidents": top_risk
    }