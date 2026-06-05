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


def build_features(incident):

    priority = PRIORITY_MAP.get(
        incident.get("priority", "medium").lower(),
        2
    )

    reassignment = int(
        incident.get("reassignment_count", 0)
    )

    document_embedding = get_document_embedding()

    features = [
        priority,
        reassignment,
    ]

    features.extend(document_embedding)

    return [features]


def predict_risk(incident):

    try:

        features = build_features(incident)

        probability = model.predict_proba(features)[0][1]

        ml_score = round(probability * 100, 2)

        # Rule-based boosting
        priority = incident.get("priority", "").lower()

        title = (
            incident.get("title", "") +
            " " +
            incident.get("description", "")
        ).lower()

        if priority == "critical":
            ml_score += 35

        keywords = [
            "payment",
            "refund",
            "database",
            "outage",
            "security",
            "authentication",
            "server",
            "failure",
            "gateway"
        ]

        if any(k in title for k in keywords):
            ml_score += 25

        if incident.get("assignee") == "Unassigned":
            ml_score += 10

        return min(100, round(ml_score, 2))

    except Exception as e:

        print("ML PREDICTION ERROR =", str(e))

        # Safe fallback score
        return 75