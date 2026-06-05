import requests
import logging
from datetime import datetime, timezone
from typing import Tuple, List, Dict, Any
from services.connectors.base_connector import BaseConnector

logger = logging.getLogger(__name__)

PRIORITY_MAP = {
    "Highest": "critical",
    "High":    "high",
    "Medium":  "medium",
    "Low":     "low",
    "Lowest":  "low",
}

class JiraConnector(BaseConnector):

    def _auth(self):
        return (self.username, self.api_token)

    def _headers(self):
        return {"Accept": "application/json", "Content-Type": "application/json"}

    def test_connection(self) -> Tuple[bool, str]:
        try:
            url = f"{self.base_url}/rest/api/3/myself"
            r = requests.get(url, auth=self._auth(), headers=self._headers(), timeout=10)
            if r.status_code != 200:
                return False, f"HTTP {r.status_code}: {r.text[:200]}"
            
            if self.app_id:
                proj_url = f"{self.base_url}/rest/api/3/project/{self.app_id}"
                r_proj = requests.get(proj_url, auth=self._auth(), headers=self._headers(), timeout=10)
                if r_proj.status_code != 200:
                    return False, f"Project '{self.app_id}' not found or no permission. (HTTP {r_proj.status_code})"
            return True, "OK"
        except Exception as e:
            return False, str(e)

    def fetch_tickets(self, since: datetime | None = None) -> List[Dict[str, Any]]:
        """Fetch issues updated since `since` using JQL pagination."""
        project_clause = f"project = '{self.app_id}'" if self.app_id else "project IS NOT EMPTY"
        jql = f'{project_clause} ORDER BY updated DESC'
        if since:
            ts = since.strftime("%Y-%m-%d %H:%M")
            jql = f'{project_clause} AND updated >= "{ts}" ORDER BY updated DESC'

        url = f"{self.base_url}/rest/api/3/search/jql"
        start = 0
        page_size = 50
        results = []

        while True:
            params = {
                "jql": jql,
                "startAt": start,
                "maxResults": page_size,
                "fields": "summary,description,priority,status,assignee,reporter,"
                          "created,updated,resolutiondate,duedate,customfield_10016,"  # story points
                          "comment,subtasks,parent"
            }
            try:
                r = requests.get(url, auth=self._auth(), headers=self._headers(),
                                 params=params, timeout=15)
                r.raise_for_status()
                data = r.json()
                issues = data.get("issues", [])
                for issue in issues:
                    results.append(self.normalize(issue))
                if start + page_size >= data.get("total", 0):
                    break
                start += page_size
            except Exception as e:
                logger.error(f"[Jira] fetch_tickets error: {e}")
                break

        return results

    # def normalize(self, raw: Dict) -> Dict:
    #     f = raw.get("fields", {})
    #     priority_name = (f.get("priority") or {}).get("name", "Medium")
    #     assignee = (f.get("assignee") or {}).get("displayName", "Unassigned")
    #     reporter  = (f.get("reporter")  or {}).get("displayName", "Unknown")
    #     status    = (f.get("status")    or {}).get("name", "Open")

    #     def parse_dt(s):
    #         if not s:
    #             return None
    #         try:
    #             return datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None)
    #         except Exception:
    #             return None

    #     return {
    #         "source":             "jira",
    #         "ticket_id":          raw.get("key", ""),
    #         "title":              f.get("summary", "")[:500],
    #         "description":        str((f.get("description") or ""))[:2000],
    #         "priority":           PRIORITY_MAP.get(priority_name, "medium"),
    #         "status":             status.lower(),
    #         "assignee":           assignee[:200],
    #         "reporter":           reporter[:200],
    #         "created_at":         parse_dt(f.get("created")),
    #         "updated_at":         parse_dt(f.get("updated")),
    #         "resolved_at":        parse_dt(f.get("resolutiondate")),
    #         "sla_due_at":         parse_dt(f.get("duedate")),
    #         "reassignment_count": 0,  # requires changelog — kept simple for now
    #         "raw_data":           raw,
    #     }


    def normalize(self, raw: Dict) -> Dict:
        f = raw.get("fields", {})
        priority_name = (f.get("priority") or {}).get("name", "Medium")
        assignee = (f.get("assignee") or {}).get("displayName", "Unassigned")
        reporter = (f.get("reporter") or {}).get("displayName", "Unknown")
        status = (f.get("status") or {}).get("name", "Open")

        def parse_dt(s):
            if not s:
                return None
            try:
                return datetime.fromisoformat(
                    s.replace("Z", "+00:00")
                ).replace(tzinfo=None)
            except Exception:
                return None

        def build_sla_due_at(created_str, due_str):
            """
            Use Jira due date but preserve the time from created_at.
            """
            if not due_str:
                return None

            try:
                due_dt_parsed = parse_dt(due_str)
                if not due_dt_parsed:
                    return None
                    
                due_date = due_dt_parsed.date()
                created_dt = parse_dt(created_str)

                if created_dt:
                    return datetime.combine(due_date, created_dt.time())

                return datetime.combine(due_date, datetime.min.time())

            except Exception as e:
                logger.error(f"[Jira] Error building sla_due_at: {e}")
                return None

        created_at = parse_dt(f.get("created"))

        return {
            "source": "jira",
            "ticket_id": raw.get("key", ""),
            "title": f.get("summary", "")[:500],
            "description": str((f.get("description") or ""))[:2000],
            "priority": PRIORITY_MAP.get(priority_name, "medium"),
            "status": status.lower(),
            "assignee": assignee[:200],
            "reporter": reporter[:200],

            "created_at": created_at,
            "updated_at": parse_dt(f.get("updated")),
            "resolved_at": parse_dt(f.get("resolutiondate")),

            # Due date with created time preserved
            "sla_due_at": build_sla_due_at(
                f.get("created"),
                f.get("duedate")
            ),

            "reassignment_count": 0,
            "raw_data": raw,
        }