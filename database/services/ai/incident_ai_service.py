import json
import logging
from database.db_connection import get_db_connection
from services.ml.hybrid_risk_predictor import predict_risk
from services.ai.chroma_service import ChromaService
from services.ai.mistral_service import MistralService

logger = logging.getLogger(__name__)


class IncidentAIService:

    @staticmethod
    def process_incident(incident: dict):

        try:

            incident_text = f"""
Title: {incident.get('title')}

Description:
{incident.get('description')}

Priority:
{incident.get('priority')}

Status:
{incident.get('status')}

Assignee:
{incident.get('assignee')}
"""

            metadata = {
                "source": incident.get("source"),
                "priority": incident.get("priority"),
                "status": incident.get("status"),
            }

            chroma_id = f"{incident.get('source')}-{incident.get('ticket_id')}"

            # Search ChromaDB for similar past incidents BEFORE storing this one
            similar_docs = ChromaService.search_similar(incident_text, top_k=1)
            docs = similar_docs.get("documents", [[]])[0]
            if len(docs) == 0:
                new_ticket_score = 20.0
            else:
                new_ticket_score = 5.0

            # Store in ChromaDB
            ChromaService.store_incident(
                incident_id=chroma_id,
                text=incident_text,
                metadata=metadata
            )

            # AI Analysis
            ai_result = MistralService.analyze_incident(
                incident_text
            )
            # ML Model outputs 0-100, scale to 0-20
            ml_risk_score = predict_risk(incident)
            sla_breach_score = ml_risk_score / 5.0

            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT id FROM incidents
                WHERE source = %s
                AND ticket_id = %s
                LIMIT 1
            """, (
                incident.get("source"),
                incident.get("ticket_id")
            ))

            row = cursor.fetchone()

            if not row:
                return

            incident_db_id = row[0]

            # Prevent duplicate AI analysis
            cursor.execute("""
                SELECT id
                FROM incident_ai_analysis
                WHERE incident_id = %s
                LIMIT 1
            """, (incident_db_id,))

            existing = cursor.fetchone()

            if existing:

                logger.info(
                    f"[AI] Analysis already exists for {incident.get('ticket_id')}"
                )

                cursor.close()
                conn.close()

                return

            cursor.execute("""
                INSERT INTO incident_ai_analysis
                (
                    incident_id,
                    summary,
                    solution,
                    risk_score,
                    estimated_resolution_time,
                    impact_score,
                    urgency_score,
                    complexity_score,
                    sla_breach_score,
                    new_ticket_score
                )
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                incident_db_id,
                ai_result.get("summary"),
                ai_result.get("solution"),
                0, # risk_score is calculated fully in risk_scoring_job
                ai_result.get("estimated_resolution_time"),
                ai_result.get("impact_score", 0),
                ai_result.get("urgency_score", 0),
                ai_result.get("complexity_score", 0),
                sla_breach_score,
                new_ticket_score
            ))

            conn.commit()

            cursor.close()
            conn.close()

            logger.info(
                f"[AI] Processed incident {incident.get('ticket_id')}"
            )

        except Exception as e:

            import traceback

            print("\n========== AI PROCESSING ERROR ==========")
            print(str(e))
            traceback.print_exc()
            print("=========================================\n")

            logger.error(f"[AI] Processing failed: {e}")