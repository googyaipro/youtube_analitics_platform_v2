import os
from typing import Any, Dict, List, Optional
import requests
import streamlit as st

DEFAULT_API_URL = os.getenv("BACKEND_API_URL", "http://backend:8080/api/v1")
if "localhost" in os.getenv("HOSTNAME", "") or not os.getenv("DOKPLOY_API_DOMAIN"):
    # If running on local workstation outside docker network
    DEFAULT_API_URL = os.getenv("BACKEND_API_URL", "http://localhost:8000/api/v1")


class APIClient:
    def __init__(self, base_url: str = DEFAULT_API_URL):
        self.base_url = base_url.rstrip("/")

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        token = st.session_state.get("access_token")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    # --- Authentication ---
    def login(self, email: str, password: str) -> Dict[str, Any]:
        url = f"{self.base_url}/auth/login"
        resp = requests.post(url, json={"email": email, "password": password}, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def register(self, email: str, password: str, full_name: Optional[str] = None, language: str = "ru") -> Dict[str, Any]:
        url = f"{self.base_url}/auth/register"
        resp = requests.post(url, json={
            "email": email,
            "password": password,
            "full_name": full_name,
            "language": language
        }, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def get_me(self) -> Dict[str, Any]:
        url = f"{self.base_url}/auth/me"
        resp = requests.get(url, headers=self._headers(), timeout=10)
        resp.raise_for_status()
        return resp.json()

    def update_user_language(self, language: str) -> Dict[str, Any]:
        url = f"{self.base_url}/auth/me/language"
        resp = requests.put(url, json={"language": language}, params={"language": language}, headers=self._headers(), timeout=10)
        return resp.json() if resp.status_code == 200 else {}


    # --- Profile & BYOK Keys ---
    def update_user_keys(self, youtube_key: Optional[str] = None, gemini_key: Optional[str] = None) -> Dict[str, Any]:
        url = f"{self.base_url}/user/keys"
        payload = {}
        if youtube_key is not None:
            payload["youtube_api_key"] = youtube_key
        if gemini_key is not None:
            payload["gemini_api_key"] = gemini_key
        resp = requests.put(url, json=payload, headers=self._headers(), timeout=15)
        resp.raise_for_status()
        return resp.json()

    def verify_key(self, key_type: str, api_key: str) -> Dict[str, Any]:
        url = f"{self.base_url}/user/verify-key"
        resp = requests.post(url, json={"key_type": key_type, "api_key": api_key}, headers=self._headers(), timeout=20)
        resp.raise_for_status()
        return resp.json()

    def generate_telegram_link(self) -> Dict[str, Any]:
        url = f"{self.base_url}/user/telegram-link"
        resp = requests.post(url, headers=self._headers(), timeout=10)
        resp.raise_for_status()
        return resp.json()

    # --- Channel Sets (Workspaces) ---
    def get_channel_sets(self) -> List[Dict[str, Any]]:
        url = f"{self.base_url}/channel-sets"
        resp = requests.get(url, headers=self._headers(), timeout=10)
        return resp.json() if resp.status_code == 200 else []

    def create_channel_set(self, data: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base_url}/channel-sets"
        resp = requests.post(url, json=data, headers=self._headers(), timeout=15)
        resp.raise_for_status()
        return resp.json()

    def update_channel_set(self, set_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base_url}/channel-sets/{set_id}"
        resp = requests.put(url, json=data, headers=self._headers(), timeout=15)
        resp.raise_for_status()
        return resp.json()

    def delete_channel_set(self, set_id: str) -> Dict[str, Any]:
        url = f"{self.base_url}/channel-sets/{set_id}"
        resp = requests.delete(url, headers=self._headers(), timeout=15)
        resp.raise_for_status()
        return resp.json()

    def activate_channel_set(self, set_id: str) -> Dict[str, Any]:
        url = f"{self.base_url}/channel-sets/{set_id}/activate"
        resp = requests.post(url, headers=self._headers(), timeout=10)
        resp.raise_for_status()
        return resp.json()

    def sync_channel_set(self, set_id: str) -> Dict[str, Any]:
        url = f"{self.base_url}/channel-sets/{set_id}/sync"
        resp = requests.post(url, headers=self._headers(), timeout=60)
        resp.raise_for_status()
        return resp.json()

    # --- Channels ---
    def get_channels(self, set_id: Optional[str] = None) -> List[Dict[str, Any]]:
        url = f"{self.base_url}/channels"
        params = {"set_id": set_id} if set_id else {}
        resp = requests.get(url, params=params, headers=self._headers(), timeout=10)
        return resp.json() if resp.status_code == 200 else []

    def add_channel(self, channel_url_or_handle: str, set_id: Optional[str] = None) -> Dict[str, Any]:
        url = f"{self.base_url}/channels"
        params = {"set_id": set_id} if set_id else {}
        resp = requests.post(url, json={"channel_url_or_handle": channel_url_or_handle}, params=params, headers=self._headers(), timeout=30)
        resp.raise_for_status()
        return resp.json()

    def delete_channel(self, channel_id: str, set_id: Optional[str] = None) -> Dict[str, Any]:
        url = f"{self.base_url}/channels/{channel_id}"
        params = {"set_id": set_id} if set_id else {}
        resp = requests.delete(url, params=params, headers=self._headers(), timeout=15)
        resp.raise_for_status()
        return resp.json()

    # --- Videos & KPIs ---
    def get_videos(self, set_id: Optional[str] = None, channel_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        url = f"{self.base_url}/videos"
        params = {"limit": limit}
        if set_id:
            params["set_id"] = set_id
        if channel_id:
            params["channel_id"] = channel_id
        resp = requests.get(url, params=params, headers=self._headers(), timeout=15)
        return resp.json() if resp.status_code == 200 else []

    def get_kpis(self, set_id: Optional[str] = None) -> Dict[str, Any]:
        url = f"{self.base_url}/videos/kpis"
        params = {"set_id": set_id} if set_id else {}
        resp = requests.get(url, params=params, headers=self._headers(), timeout=15)
        return resp.json() if resp.status_code == 200 else {}

    def explain_video(self, video_id: str, set_id: Optional[str] = None) -> Dict[str, Any]:
        url = f"{self.base_url}/videos/{video_id}/explain"
        params = {"set_id": set_id} if set_id else {}
        resp = requests.get(url, params=params, headers=self._headers(), timeout=45)
        resp.raise_for_status()
        return resp.json()

    def ask_ai_analyst(self, query: str, set_id: Optional[str] = None, target_language: Optional[str] = None) -> Dict[str, Any]:
        url = f"{self.base_url}/analyze"
        payload = {"query": query}
        if set_id:
            payload["set_id"] = set_id
        if target_language:
            payload["target_language"] = target_language
        resp = requests.post(url, json=payload, headers=self._headers(), timeout=45)
        resp.raise_for_status()
        return resp.json()


def get_api_client() -> APIClient:
    """Singleton getter for APIClient."""
    if "api_client" not in st.session_state:
        st.session_state["api_client"] = APIClient()
    return st.session_state["api_client"]
