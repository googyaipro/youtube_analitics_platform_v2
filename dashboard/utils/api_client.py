import os
from typing import Any, Dict, List, Optional
import requests

API_URL = os.getenv("BACKEND_API_URL", "http://localhost:8000/api/v1")


class APIClient:
    def __init__(self, base_url: str = API_URL):
        self.base_url = base_url.rstrip("/")

    def get_kpis(self) -> Dict[str, Any]:
        try:
            resp = requests.get(f"{self.base_url}/videos/kpis", timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            return {"error": str(e)}

    def get_channels(self) -> List[Dict[str, Any]]:
        try:
            resp = requests.get(f"{self.base_url}/channels", timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return []

    def get_videos(self, channel_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        try:
            params = {"limit": limit}
            if channel_id:
                params["channel_id"] = channel_id
            resp = requests.get(f"{self.base_url}/videos", params=params, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return []

    def trigger_sync(self, channel_identifier: str, max_videos: int = 20) -> Dict[str, Any]:
        try:
            payload = {
                "channel_identifier": channel_identifier,
                "max_videos": max_videos
            }
            resp = requests.post(f"{self.base_url}/ingestion/sync", json=payload, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            return {"status": "ERROR", "message": str(e)}
