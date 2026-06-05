from database.db_connection import get_db_connection
from services.connectors.jira_connector import JiraConnector
from services.connectors.servicenow_connector import ServiceNowConnector

CONNECTOR_MAP = {
    "jira": JiraConnector,
    "servicenow": ServiceNowConnector,
}

def register_connector(connector_type: str, base_url: str, username: str, api_token: str, app_id: str = None):
    ctype = connector_type.lower()
    if ctype not in CONNECTOR_MAP:
        return {"error": f"Unknown connector type: {ctype}"}

    # Automatically strip any copy-pasted whitespace
    base_url = base_url.strip().rstrip("/")
    if ctype == "servicenow":
        if not base_url.startswith("http://") and not base_url.startswith("https://"):
            if "." not in base_url:
                base_url = f"https://{base_url}.service-now.com"
            else:
                base_url = f"https://{base_url}"
    username = username.strip()
    api_token = api_token.strip()
    if app_id:
        app_id = app_id.strip()

    cls = CONNECTOR_MAP[ctype]
    svc = cls(base_url, username, api_token, app_id)
    ok, msg = svc.test_connection()
    if not ok:
        return {"error": f"Connection failed: {msg}"}

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO connector_configs (connector_type, base_url, username, api_token, app_id, is_active)
        VALUES (%s, %s, %s, %s, %s, 1)
        ON DUPLICATE KEY UPDATE
            base_url   = VALUES(base_url),
            username   = VALUES(username),
            api_token  = VALUES(api_token),
            app_id     = VALUES(app_id),
            is_active  = 1,
            updated_at = CURRENT_TIMESTAMP
    """, (ctype, base_url, username, api_token, app_id))
    conn.commit()
    cursor.close()
    conn.close()

    return {"message": f"{ctype} connected successfully"}

def list_active_connectors():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # ADDED: WHERE is_active = 1
    cursor.execute("""
        SELECT id, connector_type, base_url, username, app_id, is_active, last_synced_at, created_at
        FROM connector_configs
        WHERE is_active = 1 
    """)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    for r in rows:
        if r["last_synced_at"]: r["last_synced_at"] = r["last_synced_at"].isoformat()
        if r["created_at"]: r["created_at"] = r["created_at"].isoformat()

    return {"connectors": rows}

def deactivate_connector(connector_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE connector_configs SET is_active = 0 WHERE id = %s", (connector_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return {"message": "Connector deactivated"}
