import joblib
import pandas as pd

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from services.ai.embedding_service import EmbeddingService
from database.db_connection import get_db_connection


PRIORITY_MAP = {
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4
}


conn = get_db_connection()
cursor = conn.cursor()

query = """
SELECT
    priority,
    reassignment_count,
    created_at,
    resolved_at
FROM incidents
WHERE resolved_at IS NOT NULL
"""

df = pd.read_sql(query, conn)
doc_query = """
SELECT raw_summary
FROM uploaded_documents
"""

doc_df = pd.read_sql(doc_query, conn)

conn.close()
embedding_features = []

for text in doc_df["raw_summary"]:

    embedding = EmbeddingService.generate_embedding(
        text or ""
    )

    embedding_features.append(
        embedding[:10]
    )


df["priority"] = df["priority"].map(PRIORITY_MAP)

df["incident_age_hours"] = (
    (
        df["resolved_at"] - df["created_at"]
    ).dt.total_seconds() / 3600
)

df["breached"] = (
    df["incident_age_hours"] > 8
).astype(int)


base_features = df[
    [
        "priority",
        "reassignment_count",
        "incident_age_hours"
    ]
].values.tolist()

X = []

for i in range(len(base_features)):

    combined = (
        base_features[i]
        +
        embedding_features[i % len(embedding_features)]
    )

    X.append(combined)

y = df["breached"]


X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
    random_state=42
)


model = RandomForestClassifier()

model.fit(X_train, y_train)

joblib.dump(
    model,
    "services/ml/models/sla_model.pkl"
)

print("MODEL TRAINED SUCCESSFULLY")