import os
from typing import Any, Dict, List, Optional
import requests

API_URL = os.getenv("BACKEND_API_URL", "http://localhost:8000/api")


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

    def ask_ai_analyst(self, query: str) -> Dict[str, Any]:
        try:
            resp = requests.post(f"{self.base_url}/analyze", json={"query": query}, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            return {"error": str(e)}

    def add_competitor(self, handle_or_url: str) -> Dict[str, Any]:
        try:
            payload = {"channel_url_or_handle": handle_or_url}
            resp = requests.post(f"{self.base_url}/competitors", json=payload, timeout=20)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            return {"status": "ERROR", "message": str(e)}

    def delete_competitor(self, channel_id: str) -> Dict[str, Any]:
        try:
            resp = requests.delete(f"{self.base_url}/competitors/{channel_id}", timeout=15)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            return {"status": "ERROR", "message": str(e)}

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

    def get_telegram_subscribers(self) -> List[Dict[str, Any]]:
        try:
            resp = requests.get(f"{self.base_url}/telegram/subscribers", timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return []
