import logging
import os
from typing import Any, Dict, List, Optional
import requests
import streamlit as st

logger = logging.getLogger("dashboard.api_client")


def _build_candidate_urls(custom_base: Optional[str] = None) -> List[str]:
    """Build prioritized list of candidate URLs for connecting to FastAPI backend."""
    candidates = []
    if custom_base:
        candidates.append(custom_base.rstrip("/"))

    env_backend = os.getenv("BACKEND_API_URL")
    if env_backend and env_backend.strip():
        clean_env = env_backend.strip().rstrip("/")
        if clean_env not in candidates:
            candidates.append(clean_env)

    dokploy_api = os.getenv("DOKPLOY_API_DOMAIN", "api.yap.oxyjet.win").strip()
    public_url = f"https://{dokploy_api}/api/v1"

    defaults = [
        "http://backend:8080/api/v1",
        "http://yap_backend:8080/api/v1",
        public_url,
        "http://localhost:8080/api/v1",
        "http://localhost:8000/api/v1",
        "http://127.0.0.1:8080/api/v1",
    ]

    for d in defaults:
        if d not in candidates:
            candidates.append(d)

    return candidates


class APIClient:
    def __init__(self, base_url: Optional[str] = None):
        self.candidate_urls = _build_candidate_urls(base_url)
        self.base_url = self.candidate_urls[0]

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        token = st.session_state.get("access_token")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        """
        Execute an HTTP request with automatic failover across candidate URLs
        if a network, DNS resolution, or gateway connection error occurs.
        """
        path = path.lstrip("/")
        if "timeout" not in kwargs:
            kwargs["timeout"] = 15

        headers = self._headers()
        if "headers" in kwargs:
            merged = headers.copy()
            merged.update(kwargs["headers"])
            kwargs["headers"] = merged
        else:
            kwargs["headers"] = headers

        # Try active base_url first, followed by remaining candidates
        urls_to_try = [self.base_url] + [u for u in self.candidate_urls if u != self.base_url]
        last_exception = None

        for base in urls_to_try:
            url = f"{base}/{path}"
            try:
                resp = requests.request(method, url, **kwargs)
                # If we received a response with status not in (502, 503, 504), backend is alive
                if resp.status_code not in (502, 503, 504):
                    if base != self.base_url:
                        logger.info(f"APIClient successfully switched active backend to: {base}")
                        self.base_url = base
                    return resp
                # If 502/503/504 Bad Gateway from proxy, try other candidate
                last_exception = requests.exceptions.HTTPError(
                    f"HTTP {resp.status_code} Bad Gateway from {base}"
                )
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                last_exception = e
                logger.warning(f"Connection to {url} failed: {e}. Attempting next candidate...")
                continue

        error_detail = (
            f"Cannot connect to YouTube Analytics Backend. "
            f"Attempted endpoints: {urls_to_try}. "
            f"Last error: {last_exception}"
        )
        raise requests.exceptions.ConnectionError(error_detail)

    # --- Authentication ---
    def login(self, email: str, password: str) -> Dict[str, Any]:
        resp = self._request("POST", "auth/login", json={"email": email, "password": password}, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def register(self, email: str, password: str, full_name: Optional[str] = None, language: str = "en") -> Dict[str, Any]:
        resp = self._request("POST", "auth/register", json={
            "email": email,
            "password": password,
            "full_name": full_name,
            "language": language
        }, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def get_me(self) -> Dict[str, Any]:
        resp = self._request("GET", "auth/me", timeout=10)
        resp.raise_for_status()
        return resp.json()

    def update_user_language(self, language: str) -> Dict[str, Any]:
        resp = self._request("PUT", "auth/me/language", json={"language": language}, params={"language": language}, timeout=10)
        return resp.json() if resp.status_code == 200 else {}

    # --- Profile & BYOK Keys ---
    def update_user_keys(self, youtube_key: Optional[str] = None, gemini_key: Optional[str] = None) -> Dict[str, Any]:
        payload = {}
        if youtube_key is not None:
            payload["youtube_api_key"] = youtube_key
        if gemini_key is not None:
            payload["gemini_api_key"] = gemini_key
        resp = self._request("PUT", "user/keys", json=payload, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def verify_key(self, key_type: str, api_key: str) -> Dict[str, Any]:
        resp = self._request("POST", "user/verify-key", json={"key_type": key_type, "api_key": api_key}, timeout=20)
        resp.raise_for_status()
        return resp.json()

    def generate_telegram_link(self) -> Dict[str, Any]:
        resp = self._request("POST", "user/telegram-link", timeout=10)
        resp.raise_for_status()
        return resp.json()

    # --- Channel Sets (Workspaces) ---
    def get_channel_sets(self) -> List[Dict[str, Any]]:
        try:
            resp = self._request("GET", "channel-sets", timeout=10)
            return resp.json() if resp.status_code == 200 else []
        except Exception as e:
            logger.warning(f"Error fetching channel sets: {e}")
            return []

    def create_channel_set(self, data: Dict[str, Any]) -> Dict[str, Any]:
        resp = self._request("POST", "channel-sets", json=data, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def update_channel_set(self, set_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        resp = self._request("PUT", f"channel-sets/{set_id}", json=data, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def delete_channel_set(self, set_id: str) -> Dict[str, Any]:
        resp = self._request("DELETE", f"channel-sets/{set_id}", timeout=15)
        resp.raise_for_status()
        return resp.json()

    def activate_channel_set(self, set_id: str) -> Dict[str, Any]:
        resp = self._request("POST", f"channel-sets/{set_id}/activate", timeout=10)
        resp.raise_for_status()
        return resp.json()

    def sync_channel_set(self, set_id: str) -> Dict[str, Any]:
        resp = self._request("POST", f"channel-sets/{set_id}/sync", timeout=90)
        resp.raise_for_status()
        return resp.json()

    # --- Channels ---
    def get_channels(self, set_id: Optional[str] = None) -> List[Dict[str, Any]]:
        try:
            params = {"set_id": set_id} if set_id else {}
            resp = self._request("GET", "channels", params=params, timeout=10)
            return resp.json() if resp.status_code == 200 else []
        except Exception as e:
            logger.warning(f"Error fetching channels: {e}")
            return []

    def add_channel(self, channel_url_or_handle: str, set_id: Optional[str] = None) -> Dict[str, Any]:
        params = {"set_id": set_id} if set_id else {}
        resp = self._request(
            "POST",
            "channels",
            json={"channel_url_or_handle": channel_url_or_handle},
            params=params,
            timeout=30
        )
        resp.raise_for_status()
        return resp.json()

    def delete_channel(self, channel_id: str, set_id: Optional[str] = None) -> Dict[str, Any]:
        params = {"set_id": set_id} if set_id else {}
        resp = self._request("DELETE", f"channels/{channel_id}", params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def get_channel_set_digest(self, set_id: str) -> Dict[str, Any]:
        resp = self._request("GET", f"channel-sets/{set_id}/digest", timeout=60)
        resp.raise_for_status()
        return resp.json()

    # --- Videos & KPIs ---
    def get_videos(
        self,
        set_id: Optional[str] = None,
        channel_id: Optional[str] = None,
        format_filter: Optional[str] = "all",
        sort_by: Optional[str] = "views",
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        try:
            params = {"limit": limit}
            if set_id:
                params["set_id"] = set_id
            if channel_id:
                params["channel_id"] = channel_id
            if format_filter:
                params["format_filter"] = format_filter
            if sort_by:
                params["sort_by"] = sort_by
            resp = self._request("GET", "videos", params=params, timeout=15)
            return resp.json() if resp.status_code == 200 else []
        except Exception as e:
            logger.warning(f"Error fetching videos: {e}")
            return []

    def get_kpis(self, set_id: Optional[str] = None) -> Dict[str, Any]:
        try:
            params = {"set_id": set_id} if set_id else {}
            resp = self._request("GET", "videos/kpis", params=params, timeout=15)
            return resp.json() if resp.status_code == 200 else {}
        except Exception as e:
            logger.warning(f"Error fetching kpis: {e}")
            return {}

    def explain_video(self, video_id: str, set_id: Optional[str] = None) -> Dict[str, Any]:
        params = {"set_id": set_id} if set_id else {}
        resp = self._request("GET", f"videos/{video_id}/explain", params=params, timeout=45)
        resp.raise_for_status()
        return resp.json()

    def ask_ai_analyst(self, query: str, set_id: Optional[str] = None, target_language: Optional[str] = None) -> Dict[str, Any]:
        payload = {"query": query}
        if set_id:
            payload["set_id"] = set_id
        if target_language:
            payload["target_language"] = target_language
        resp = self._request("POST", "analyze", json=payload, timeout=45)
        resp.raise_for_status()
        return resp.json()

    # --- Administration Endpoints ---
    def claim_admin(self, admin_secret: str) -> Dict[str, Any]:
        resp = self._request("POST", "admin/claim", json={"admin_secret": admin_secret}, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def get_admin_stats(self) -> Dict[str, Any]:
        resp = self._request("GET", "admin/stats", timeout=10)
        resp.raise_for_status()
        return resp.json()

    def get_admin_users(self) -> List[Dict[str, Any]]:
        resp = self._request("GET", "admin/users", timeout=15)
        resp.raise_for_status()
        return resp.json()

    def toggle_user_active(self, user_id: str) -> Dict[str, Any]:
        resp = self._request("POST", f"admin/users/{user_id}/toggle-active", timeout=10)
        resp.raise_for_status()
        return resp.json()

    def toggle_user_admin(self, user_id: str) -> Dict[str, Any]:
        resp = self._request("POST", f"admin/users/{user_id}/toggle-admin", timeout=10)
        resp.raise_for_status()
        return resp.json()

    def delete_user(self, user_id: str) -> Dict[str, Any]:
        resp = self._request("DELETE", f"admin/users/{user_id}", timeout=15)
        resp.raise_for_status()
        return resp.json()

    def get_admin_telegram_status(self) -> Dict[str, Any]:
        resp = self._request("GET", "admin/telegram-status", timeout=15)
        resp.raise_for_status()
        return resp.json()

    def setup_admin_telegram_webhook(self) -> Dict[str, Any]:
        resp = self._request("POST", "admin/telegram-setup-webhook", timeout=15)
        resp.raise_for_status()
        return resp.json()

    def send_telegram_test(self) -> Dict[str, Any]:
        resp = self._request("POST", "user/telegram-test", timeout=15)
        resp.raise_for_status()
        return resp.json()

    # --- Telemetry & Logs ---
    def get_ai_logs(
        self,
        limit: int = 50,
        offset: int = 0,
        status: Optional[str] = None,
        operation: Optional[str] = None,
        search: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        params = {"limit": limit, "offset": offset}
        if status and status != "ALL":
            params["status"] = status
        if operation and operation != "ALL":
            params["operation"] = operation
        if search and search.strip():
            params["search"] = search.strip()
        resp = self._request("GET", "logs/ai", params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def get_ai_stats(self) -> Dict[str, Any]:
        resp = self._request("GET", "logs/ai/stats", timeout=10)
        resp.raise_for_status()
        return resp.json()

    def get_system_logs(
        self,
        limit: int = 50,
        offset: int = 0,
        category: Optional[str] = None,
        level: Optional[str] = None,
        search: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        params = {"limit": limit, "offset": offset}
        if category and category != "ALL":
            params["category"] = category
        if level and level != "ALL":
            params["level"] = level
        if search and search.strip():
            params["search"] = search.strip()
        resp = self._request("GET", "logs/system", params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def clear_logs(self, log_type: str = "all") -> Dict[str, Any]:
        resp = self._request("POST", "logs/clear", json={"log_type": log_type}, timeout=15)
        resp.raise_for_status()
        return resp.json()


def get_api_client() -> APIClient:
    """Singleton getter for APIClient."""
    if "api_client" not in st.session_state:
        st.session_state["api_client"] = APIClient()
    return st.session_state["api_client"]
