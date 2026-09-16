import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from google.cloud import storage
from config.settings import get_settings

logger = logging.getLogger(__name__)


class StorageService:
    def __init__(self, bucket_name: Optional[str] = None):
        settings = get_settings()
        self.bucket_name = bucket_name or settings.GCS_BUCKET_NAME
        self.project_id = settings.GCP_PROJECT_ID
        self._client: Optional[storage.Client] = None
        self._local_backup_dir = Path("./data/raw_backups")
        self._local_backup_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            self._client = storage.Client(project=self.project_id)
            logger.info("Google Cloud Storage client initialized.")
        except Exception as e:
            logger.warning(f"GCS client initialization failed (will fallback to local disk): {e}")

    @property
    def is_connected(self) -> bool:
        return self._client is not None

    def upload_raw_json(self, destination_blob_name: str, data: Dict[str, Any]) -> str:
        """Uploads JSON dictionary to GCS or stores to local disk if GCS is unavailable."""
        payload_bytes = json.dumps(data, default=str, indent=2).encode("utf-8")
        
        if self.is_connected:
            try:
                bucket = self._client.bucket(self.bucket_name)
                blob = bucket.blob(destination_blob_name)
                blob.upload_from_string(payload_bytes, content_type="application/json")
                uri = f"gs://{self.bucket_name}/{destination_blob_name}"
                logger.info(f"Raw data successfully saved to {uri}")
                return uri
            except Exception as e:
                logger.warning(f"Failed to upload to GCS ({e}). Saving to local backup.")

        # Local fallback
        local_path = self._local_backup_dir / destination_blob_name
        local_path.parent.mkdir(parents=True, exist_ok=True)
        with open(local_path, "wb") as f:
            f.write(payload_bytes)
        logger.info(f"Raw data saved locally at {local_path}")
        return str(local_path)
