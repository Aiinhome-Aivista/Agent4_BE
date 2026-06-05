from abc import ABC, abstractmethod
from typing import Tuple, List, Dict, Any
from datetime import datetime

class BaseConnector(ABC):
    """Abstract base for all external system connectors."""

    def __init__(self, base_url: str, username: str, api_token: str, app_id: str = None):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.api_token = api_token
        self.app_id = app_id

    @abstractmethod
    def test_connection(self) -> Tuple[bool, str]:
        """Validate credentials. Returns (ok, message)."""
        ...

    @abstractmethod
    def fetch_tickets(self, since: datetime | None = None) -> List[Dict[str, Any]]:
        """Fetch tickets updated since `since`. Return normalized list."""
        ...

    def normalize(self, raw: Dict) -> Dict:
        """Subclasses override to normalize raw API response to common schema."""
        return raw
