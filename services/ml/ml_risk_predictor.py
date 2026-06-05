import joblib
from datetime import datetime

MODEL_PATH = "services/ml/models/sla_model.pkl"

model = joblib.load(MODEL_PATH)


PRIORITY_MAP = {
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4
}


from database.db_connection import get_db_connection
from services.ai.embedding_service import EmbeddingService

DOCUMENT_EMBEDDING_CACHE = None

def get_document_embedding():
    global DOCUMENT_EMBEDDING_CACHE
    if DOCUMENT_EMBEDDING_CACHE is not None:
        return DOCUMENT_EMBEDDING_CACHE
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT raw_summary
            FROM uploaded_documents
            ORDER BY uploaded_at DESC
            LIMIT 1
        """)
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        if not row:
            DOCUMENT_EMBEDDING_CACHE = [0] * 10
            return DOCUMENT_EMBEDDING_CACHE
        summary = row["raw_summary"] or ""
        embedding = EmbeddingService.generate_embedding(summary)
        DOCUMENT_EMBEDDING_CACHE = embedding[:10]
        return DOCUMENT_EMBEDDING_CACHE
    except Exception as e:
        print("DOCUMENT EMBEDDING ERROR =", str(e))
        return [0] * 10

def build_features(incident: dict):

    priority = PRIORITY_MAP.get(
        incident.get("priority", "medium").lower(),
        2
    )

    reassignment_count = int(
        incident.get("reassignment_count", 0)
    )

    created_at = incident.get("created_at")

    incident_age_hours = 0

    if created_at and isinstance(created_at, datetime):

        incident_age_hours = (
            datetime.utcnow() - created_at
        ).total_seconds() / 3600

    document_embedding = get_document_embedding()
    features = [
        priority,
        reassignment_count,
        incident_age_hours
    ]
    features.extend(document_embedding)

    return [features]


def predict_risk_score(incident: dict):

    features = build_features(incident)

    prediction = model.predict_proba(features)[0][1]

    return round(prediction * 100, 2)