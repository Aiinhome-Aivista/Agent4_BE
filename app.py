"""
SLA Predictive Risk Engine — FastAPI Application
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os, jwt
from fastapi import Request, Depends, Body
from pydantic import BaseModel
from fastapi import UploadFile, File
import shutil
from fastapi.responses import StreamingResponse
from services.scheduler.escalation_scheduler import (
    start_escalation_scheduler
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── Route URL prefixes ────────────────────────────────────────────────────────
AUTH_URL       = "/api/auth"
CONNECTOR_URL  = "/api/connectors"
INCIDENT_URL   = "/api/incidents"
SCHEDULER_URL  = "/api/scheduler"
DOCUMENT_URL   = "/api/documents"
CHAT_URL       = "/api/chat"


# ── Import controllers ────────────────────────────────────────────────────────
import controllers.connector_controller as connector_controller
import controllers.incident_controller as incident_controller
from services.scheduler.scheduler_manager import (
    start_scheduler, stop_scheduler, get_scheduler_status
)
from utils.auth_middleware import get_current_user
from fastapi.staticfiles import StaticFiles

UPLOAD_DIR = "uploads"
GRAPH_DIR = "graphs"


os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(GRAPH_DIR, exist_ok=True)


# ── Lifespan — startup/shutdown ───────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 SLA Engine starting...")
    start_scheduler()
    yield
    logger.info("🛑 SLA Engine shutting down...")
    stop_scheduler()


app = FastAPI(
    title="SLA Predictive Risk Engine",
    version="1.0.0",
    lifespan=lifespan,
)

app.mount(
    "/graphs",
    StaticFiles(directory="graphs"),
    name="graphs"
)
start_escalation_scheduler()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ────────────────────────────────────────────────────────────────────────────
# Auth Routes
# ────────────────────────────────────────────────────────────────────────────
class LoginBody(BaseModel):
    email: str
    password: str

@app.post(AUTH_URL + "/login")
async def login(body: LoginBody):
    from database.db_connection import get_db_connection
    import bcrypt, os, jwt
    from datetime import datetime, timedelta

    SECRET = os.getenv("JWT_SECRET", "changeme")
    EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", 24))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE email = %s", (body.email,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    if not user or not bcrypt.checkpw(body.password.encode(), user["password"].encode()):
        return JSONResponse({"error": "Invalid credentials"}, status_code=401)

    payload = {
        "sub": str(user["id"]),
        "name": user["name"],
        "email": user["email"],
        "role": user["role"],
        "exp": datetime.utcnow() + timedelta(hours=EXPIRY_HOURS),
    }
    token = jwt.encode(payload, SECRET, algorithm="HS256")
    return JSONResponse({
        "token": token,
        "user": {
            "id": user["id"],
            "name": user["name"],
            "email": user["email"],
            "role": user["role"],
        }
    })


@app.get(AUTH_URL + "/me")
async def get_me(user=Depends(get_current_user)):
    return JSONResponse({"user": user})


# ────────────────────────────────────────────────────────────────────────────
# Connector Routes
# ────────────────────────────────────────────────────────────────────────────
class ConnectorBody(BaseModel):
    connector_type: str
    base_url: str
    username: str
    api_token: str
    app_id: str = None

@app.post(CONNECTOR_URL + "/connect")
async def connect_connector(body: ConnectorBody, user=Depends(get_current_user)):
    res = connector_controller.register_connector(
        body.connector_type, body.base_url, body.username, body.api_token, body.app_id
    )
    if "error" in res:
        return JSONResponse(res, status_code=422)
    return JSONResponse(res)


@app.get(CONNECTOR_URL + "/")
async def get_connectors(user=Depends(get_current_user)):
    return JSONResponse(connector_controller.list_active_connectors())


@app.delete(CONNECTOR_URL + "/{connector_id}")
async def disconnect_connector(connector_id: int, user=Depends(get_current_user)):
    return JSONResponse(connector_controller.deactivate_connector(connector_id))


# ────────────────────────────────────────────────────────────────────────────
# Incident Routes
# ────────────────────────────────────────────────────────────────────────────
@app.get(INCIDENT_URL + "/")
async def get_incidents(
    request: Request,
    page: int = 1,
    per_page: int = 20,
    risk_level: str = "",
    source: str = "",
    user=Depends(get_current_user)
):
    return JSONResponse(incident_controller.fetch_all_incidents(page, per_page, risk_level, source))


@app.get(INCIDENT_URL + "/dashboard")
async def get_dashboard(user=Depends(get_current_user)):
    return JSONResponse(incident_controller.fetch_dashboard_metrics())


@app.get(INCIDENT_URL + "/{incident_id}")
async def get_incident(incident_id: int, user=Depends(get_current_user)):
    row = incident_controller.fetch_incident_by_id(incident_id)
    if not row:
        return JSONResponse({"error": "Incident not found"}, status_code=404)

    for k in ["created_at","updated_at","resolved_at","sla_due_at","ingested_at","calculated_at"]:
        if row.get(k):
            row[k] = row[k].isoformat()

    return JSONResponse({"incident": row})

class ChatBody(BaseModel):
    message: str
@app.post(CHAT_URL + "/{incident_id}")
async def incident_chat(
    incident_id: int,
    body: ChatBody,
    user=Depends(get_current_user)
):
    """
    Incident-scoped RAG chat endpoint.
    Streams the response as Server-Sent Events (text/event-stream).
    Guardrails restrict the LLM to only answer questions about the given incident.
    """
    from services.ai.rag_chat_service import stream_chat_response

    return StreamingResponse(
        stream_chat_response(incident_id, body.message),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )


# ────────────────────────────────────────────────────────────────────────────
# Scheduler Status Route
# ────────────────────────────────────────────────────────────────────────────
@app.get(SCHEDULER_URL + "/status")
async def scheduler_status(user=Depends(get_current_user)):
    return JSONResponse(get_scheduler_status())


@app.post(SCHEDULER_URL + "/sync")
async def trigger_sync(user=Depends(get_current_user)):
    """Manually trigger a one-off connector sync."""
    from services.scheduler.scheduler_manager import _sync_tickets_job
    import threading
    threading.Thread(target=_sync_tickets_job, daemon=True).start()
    return JSONResponse({"message": "Sync triggered", "status": "running"})

# ────────────────────────────────────────────────────────────────────────────
# Upload File
# ────────────────────────────────────────────────────────────────────────────

@app.post(DOCUMENT_URL + "/upload")
async def upload_document(
    file: UploadFile = File(...),
    user=Depends(get_current_user)
):

    from services.documents.document_processor import (
        DocumentProcessor
    )

    allowed = [".pdf", ".docx"]

    extension = os.path.splitext(
        file.filename
    )[1]

    if extension.lower() not in allowed:

        return JSONResponse(
            {
                "error": "Only PDF and DOCX files are allowed"
            },
            status_code=400
        )

    save_path = os.path.join(
        UPLOAD_DIR,
        file.filename
    )

    with open(save_path, "wb") as buffer:
        shutil.copyfileobj(
            file.file,
            buffer
        )

    result = DocumentProcessor.process_document(
        filename=file.filename,
        file_path=save_path
    )

    return JSONResponse(result) 

@app.get(DOCUMENT_URL + "/{document_id}")
async def get_document(
    document_id: int,
    user=Depends(get_current_user)
):

    from services.documents.document_processor import (
        DocumentProcessor
    )

    document = (
        DocumentProcessor.get_document_by_id(
            document_id
        )
    )

    if not document:

        return JSONResponse(
            {"error": "Document not found"},
            status_code=404
        )

    if document.get("uploaded_at"):

        document["uploaded_at"] = (
            document["uploaded_at"].isoformat()
        )

    return JSONResponse(document)

@app.get(DOCUMENT_URL)
async def get_all_documents(
    user=Depends(get_current_user)
):

    from services.documents.document_processor import (
        DocumentProcessor
    )

    documents = (
        DocumentProcessor.get_all_documents()
    )

    for document in documents:

        if document.get("uploaded_at"):

            document["uploaded_at"] = (
                document["uploaded_at"].isoformat()
            )

    return JSONResponse(documents)


# ────────────────────────────────────────────────────────────────────────────
# Health check
# ────────────────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return JSONResponse({"status": "ok", "service": "SLA Risk Engine"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=3019, reload=True)
