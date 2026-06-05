import joblib

from database.db_connection import get_db_connection
from services.ai.embedding_service import EmbeddingService


MODEL_PATH = "services/ml/models/sla_model.pkl"

model = joblib.load(MODEL_PATH)


PRIORITY_MAP = {
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4
}


# Cache embedding to avoid repeated DB calls
DOCUMENT_EMBEDDING_CACHE = None


def get_document_embedding():

    global DOCUMENT_EMBEDDING_CACHE

    # Return cached embedding if already loaded
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

        # Keep only first 10 dimensions
        DOCUMENT_EMBEDDING_CACHE = embedding[:10]

        return DOCUMENT_EMBEDDING_CACHE

    except Exception as e:

        print("DOCUMENT EMBEDDING ERROR =", str(e))

        return [0] * 10


from datetime import datetime

def build_features(incident):

    priority = PRIORITY_MAP.get(
        incident.get("priority", "medium").lower(),
        2
    )

    reassignment = int(
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
        reassignment,
        incident_age_hours
    ]

    features.extend(document_embedding)

    return [features]


def predict_risk(incident):

    try:

        features = build_features(incident)

        probability = model.predict_proba(features)[0][1]

        ml_score = round(probability * 100, 2)

        return min(100, ml_score)

    except Exception as e:

        print("ML PREDICTION ERROR =", str(e))

        # Safe fallback score
        return 75