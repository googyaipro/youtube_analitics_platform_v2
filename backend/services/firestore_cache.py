import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from google.cloud import firestore

from config.settings import get_settings

logger = logging.getLogger(__name__)


class FirestoreCache:
    """
    Operates high-performance API cache in Google Cloud Firestore (Native Mode)
    with native TTL policies on the `expires_at` field.
    """
    COLLECTION_NAME = "api_cache"

    def __init__(self):
        settings = get_settings()
        self.project_id = settings.GCP_PROJECT_ID
        self._db: Optional[firestore.Client] = None
        self._memory_cache: Dict[str, Dict[str, Any]] = {}

        try:
            self._db = firestore.Client(project=self.project_id)
            logger.info("Firestore client initialized successfully.")
        except Exception as e:
            logger.warning(f"Firestore not available ({e}), using in-memory cache fallback.")

    @property
    def is_connected(self) -> bool:
        return self._db is not None

    def get(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached JSON object if it exists and has not expired."""
        # 1. Try Firestore
        if self.is_connected:
            try:
                doc_ref = self._db.collection(self.COLLECTION_NAME).document(cache_key)
                doc = doc_ref.get()
                if doc.exists:
                    data = doc.to_dict()
                    expires_at = data.get("expires_at")
                    if expires_at and expires_at > datetime.utcnow():
                        logger.info(f"Firestore cache HIT: {cache_key}")
                        return data.get("payload")
                    else:
                        logger.info(f"Firestore cache EXPIRED: {cache_key}")
                        return None
            except Exception as e:
                logger.warning(f"Error reading from Firestore cache: {e}")

        # 2. In-memory fallback
        item = self._memory_cache.get(cache_key)
        if item:
            if item["expires_at"] > datetime.utcnow():
                logger.info(f"In-memory cache HIT: {cache_key}")
                return item["payload"]
            else:
                del self._memory_cache[cache_key]

        return None

    def set(self, cache_key: str, payload: Dict[str, Any], ttl_hours: int = 24) -> bool:
        """Store payload with expires_at for automatic TTL purge."""
        expires_at = datetime.utcnow() + timedelta(hours=ttl_hours)
        doc_data = {
            "cache_key": cache_key,
            "payload": payload,
            "created_at": datetime.utcnow(),
            "expires_at": expires_at,
        }

        # 1. Save in-memory
        self._memory_cache[cache_key] = doc_data

        # 2. Save in Firestore
        if self.is_connected:
            try:
                doc_ref = self._db.collection(self.COLLECTION_NAME).document(cache_key)
                doc_ref.set(doc_data)
                logger.info(f"Saved to Firestore cache with TTL: {cache_key}")
                return True
            except Exception as e:
                logger.warning(f"Error writing to Firestore cache: {e}")
                return False

        return True
