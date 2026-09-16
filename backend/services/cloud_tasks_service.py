import json
import logging
from typing import Any, Dict, Optional
from google.cloud import tasks_v2
from config.settings import get_settings

logger = logging.getLogger(__name__)


class CloudTasksService:
    def __init__(self):
        settings = get_settings()
        self.project_id = settings.GCP_PROJECT_ID
        self.region = settings.GCP_REGION
        self.queue_name = settings.CLOUD_TASKS_QUEUE
        self.backend_url = settings.BACKEND_PUBLIC_URL
        self._client: Optional[tasks_v2.CloudTasksClient] = None

        try:
            self._client = tasks_v2.CloudTasksClient()
            logger.info("Cloud Tasks client initialized successfully.")
        except Exception as e:
            logger.warning(f"Cloud Tasks client unavailable ({e}). Using direct background fallback.")

    @property
    def is_connected(self) -> bool:
        return self._client is not None

    def enqueue_telegram_message(
        self,
        update_data: Dict[str, Any],
        relative_path: str = "/api/tasks/process-telegram-message"
    ) -> bool:
        """Enqueue an HTTP task to Cloud Tasks to execute with full dedicated CPU."""
        if not self.is_connected:
            return False

        try:
            parent = self._client.queue_path(self.project_id, self.region, self.queue_name)
            target_url = f"{self.backend_url.rstrip('/')}{relative_path}"

            task = {
                "http_request": {
                    "http_method": tasks_v2.HttpMethod.POST,
                    "url": target_url,
                    "headers": {"Content-Type": "application/json"},
                    "body": json.dumps(update_data).encode("utf-8"),
                }
            }

            response = self._client.create_task(request={"parent": parent, "task": task})
            logger.info(f"Enqueued Cloud Task successfully: {response.name}")
            return True
        except Exception as e:
            logger.error(f"Failed to enqueue task in Cloud Tasks: {e}")
            return False
