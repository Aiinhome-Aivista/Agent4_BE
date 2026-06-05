import requests
import logging
from datetime import datetime
from typing import Tuple, List, Dict, Any
from services.connectors.base_connector import BaseConnector

logger = logging.getLogger(__name__)

PRIORITY_MAP = {
    "1": "critical",
    "2": "high",
    "3": "medium",
    "4": "low",
    "5": "low",
}

class ServiceNowConnector(BaseConnector):

    def _auth(self):
        return (self.username, self.api_token)

    def _headers(self):
        return {"Accept": "application/json", "Content-Type": "application/json"}

    def test_connection(self) -> Tuple[bool, str]:
        try:
            url = f"{self.base_url}/api/now/table/incident?sysparm_limit=1"
            r = requests.get(url, auth=self._auth(), headers=self._headers(), timeout=10)
            if r.status_code == 200:
                return True, "OK"
            return False, f"HTTP {r.status_code}: {r.text[:200]}"
        except Exception as e:
            return False, str(e)

    def fetch_tickets(self, since: datetime | None = None) -> List[Dict[str, Any]]:
        url = f"{self.base_url}/api/now/table/incident"
        query = "active=true^ORDERBYDESCsys_updated_on"
        if since:
            ts = since.strftime("%Y-%m-%d %H:%M:%S")
            query = f"sys_updated_on>={ts}^ORDERBYDESCsys_updated_on"

        offset = 0
        limit = 50
        results = []

        while True:
            params = {
                "sysparm_query": query,
                "sysparm_limit": limit,
                "sysparm_offset": offset,
                "sysparm_fields": (
                    "number,short_description,description,priority,state,"
                    "assigned_to,caller_id,opened_at,sys_updated_on,resolved_at,"
                    "due_date,reassignment_count,sys_id"
                ),
            }
            try:
                r = requests.get(url, auth=self._auth(), headers=self._headers(),
                                 params=params, timeout=15)
                r.raise_for_status()
                records = r.json().get("result", [])
                if not records:
                    break
                for rec in records:
                    results.append(self.normalize(rec))
                offset += limit
            except Exception as e:
                logger.error(f"[ServiceNow] fetch_tickets error: {e}")
                break

        return results

    def normalize(self, raw: Dict) -> Dict:
        def parse_dt(s):
            if not s:
                return None
            try:
                return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
            except Exception:
                return None

        def get_display(field):
            v = raw.get(field, "")
            if isinstance(v, dict):
                return v.get("display_value", "")
            return str(v)

        priority_num = str(raw.get("priority", "3"))
        state_map = {"1": "new", "2": "in_progress", "3": "on_hold",
                     "6": "resolved", "7": "closed"}

        created_at = parse_dt(raw.get("opened_at"))
        due_date_dt = parse_dt(raw.get("due_date"))
        
        if due_date_dt and created_at:
            sla_due_at = datetime.combine(due_date_dt.date(), created_at.time())
        else:
            sla_due_at = due_date_dt

        return {
            "source":             "servicenow",
            "ticket_id":          raw.get("number", ""),
            "title":              raw.get("short_description", "")[:500],
            "description":        raw.get("description", "")[:2000],
            "priority":           PRIORITY_MAP.get(priority_num, "medium"),
            "status":             state_map.get(str(raw.get("state", "1")), "open"),
            "assignee":           get_display("assigned_to")[:200],
            "reporter":           get_display("caller_id")[:200],
            "created_at":         created_at,
            "updated_at":         parse_dt(raw.get("sys_updated_on")),
            "resolved_at":        parse_dt(raw.get("resolved_at")),
            "sla_due_at":         sla_due_at,
            "reassignment_count": int(raw.get("reassignment_count", 0) or 0),
            "raw_data":           raw,
        }
