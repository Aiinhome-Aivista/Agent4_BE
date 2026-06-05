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

    return [[
        priority,
        reassignment_count,
        incident_age_hours
    ]]


def predict_risk_score(incident: dict):

    features = build_features(incident)

    prediction = model.predict_proba(features)[0][1]

    return round(prediction * 100, 2)