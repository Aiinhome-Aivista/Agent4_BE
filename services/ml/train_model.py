import joblib
import pandas as pd

from sklearn.linear_model import SGDClassifier
from sklearn.model_selection import train_test_split
from services.ai.embedding_service import EmbeddingService
from database.db_connection import get_db_connection
import os


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

if len(df) == 0:
    print("No resolved incidents found in the database. Cannot train model without data.")
    conn.close()
    exit(0)

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
        pd.to_datetime(df["resolved_at"]) - pd.to_datetime(df["created_at"])
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

MODEL_PATH = "services/ml/models/sla_model.pkl"

if os.path.exists(MODEL_PATH):
    print("Loading existing model for incremental training...")
    model = joblib.load(MODEL_PATH)
else:
    print("Initializing new SGDClassifier model...")
    model = SGDClassifier(loss='log_loss', random_state=42)

# Incremental training using partial_fit
model.partial_fit(X_train, y_train, classes=[0, 1])

joblib.dump(
    model,
    MODEL_PATH
)

print("MODEL TRAINED SUCCESSFULLY")