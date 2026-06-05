"""
Runs risk calculation for all open incidents and persists scores.
"""
import json
import logging
from database.db_connection import get_db_connection

logger = logging.getLogger(__name__)

def run_risk_scoring():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT * FROM incidents
        WHERE status NOT IN ('resolved','closed','done')
    """)
    incidents = cursor.fetchall()
    cursor.close()

    scored = 0
    errors = 0
    high_risk_incidents = []

    write_cursor = conn.cursor()
    for inc in incidents:
        try:
            # Fetch AI risk components
            ai_cursor = conn.cursor(dictionary=True)

            ai_cursor.execute("""
                SELECT impact_score, urgency_score, complexity_score, sla_breach_score, new_ticket_score
                FROM incident_ai_analysis
                WHERE incident_id = %s
                ORDER BY created_at DESC
                LIMIT 1
            """, (inc["id"],))

            ai_row = ai_cursor.fetchone()
            
            if not ai_row:
                ai_cursor.close()
                continue
                
            impact_score = float(ai_row.get("impact_score") or 0)
            urgency_score = float(ai_row.get("urgency_score") or 0)
            complexity_score = float(ai_row.get("complexity_score") or 0)
            sla_breach_score = float(ai_row.get("sla_breach_score") or 0)
            new_ticket_score = float(ai_row.get("new_ticket_score") or 0)
            
            final_risk = impact_score + urgency_score + complexity_score + sla_breach_score + new_ticket_score
            
            # Cap at 100
            final_risk = min(100.0, round(final_risk, 2))

            # Update risk level
            if final_risk >= 70:
                risk_level = "HIGH"
            elif final_risk >= 40:
                risk_level = "MEDIUM"
            else:
                risk_level = "LOW"

            # Update breach probability
            breach_probability = f"{round(final_risk * 1.05, 1)}%"

            reasons = [
                f"Impact Score: {impact_score}/20",
                f"Urgency Score: {urgency_score}/20",
                f"Complexity Score: {complexity_score}/20",
                f"SLA Breach Score (ML): {round(sla_breach_score, 2)}/20",
                f"New Ticket Score (Knowledge Graph): {new_ticket_score}/20"
            ]
            
            actions = ["Review 5-parameter risk component breakdown."]
            if risk_level == "HIGH":
                actions.append("Escalate immediately due to high aggregated risk.")

            ai_cursor.close()

            write_cursor.execute("""
                INSERT INTO sla_risk_scores
                    (incident_id, risk_score, risk_level, breach_probability,
                     reasons, recommended_actions)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                inc["id"],
                final_risk,
                risk_level,
                float(breach_probability.replace("%", "")),
                json.dumps(reasons),
                json.dumps(actions),
            ))
            
            result_dict = {
                "risk_score": final_risk,
                "risk_level": risk_level,
                "breach_probability": breach_probability,
                "reasons": reasons,
                "recommended_actions": actions
            }
            
            if risk_level == "HIGH":
                high_risk_incidents.append({**inc, **result_dict})
                
            scored += 1
        except Exception as e:
            logger.error(f"[Scoring] Error for incident {inc.get('id')}: {e}")
            errors += 1

    conn.commit()
    write_cursor.close()
    conn.close()

    logger.info(f"[Scoring] scored={scored}, errors={errors}, high_risk={len(high_risk_incidents)}")
    return high_risk_incidents
