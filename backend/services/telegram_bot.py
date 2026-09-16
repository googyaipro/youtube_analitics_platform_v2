import base64
import io
import logging
from typing import Optional
import httpx

from config.settings import get_settings

logger = logging.getLogger(__name__)


class TelegramBotService:
    def __init__(self, token: Optional[str] = None):
        settings = get_settings()
        self.token = token or settings.TELEGRAM_BOT_TOKEN
        self.base_url = f"https://api.telegram.org/bot{self.token}" if self.token else None

    @property
    def is_configured(self) -> bool:
        return self.base_url is not None and " " not in self.token

    def send_message(self, chat_id: int | str, text: str, parse_mode: str = "Markdown") -> bool:
        """Send a text message to Telegram user with automatic fallback if Markdown parsing fails."""
        if not self.is_configured:
            logger.info(f"[MOCK TG SEND] to {chat_id}: {text}")
            return True

        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.post(
                    f"{self.base_url}/sendMessage",
                    json={"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
                )
                if res.status_code != 200 and parse_mode:
                    logger.warning(f"Telegram Markdown parse failed ({res.text}), retrying with plain text.")
                    res = client.post(
                        f"{self.base_url}/sendMessage",
                        json={"chat_id": chat_id, "text": text}
                    )
                return res.status_code == 200
        except Exception as e:
            logger.error(f"Error sending Telegram message: {e}")
            return False

    def send_photo(
        self,
        chat_id: int | str,
        png_base64: str,
        caption: Optional[str] = None
    ) -> bool:
        """Send a base64 encoded PNG chart to Telegram with fallback for caption format."""
        if not self.is_configured:
            logger.info(f"[MOCK TG PHOTO] to {chat_id} with caption: {caption}")
            return True

        try:
            image_bytes = base64.b64decode(png_base64)
            files = {"photo": ("chart.png", image_bytes, "image/png")}
            data = {"chat_id": chat_id}
            if caption:
                data["caption"] = caption
                data["parse_mode"] = "Markdown"

            with httpx.Client(timeout=20.0) as client:
                res = client.post(f"{self.base_url}/sendPhoto", data=data, files=files)
                if res.status_code != 200 and caption and "parse_mode" in data:
                    del data["parse_mode"]
                    files = {"photo": ("chart.png", image_bytes, "image/png")}
                    res = client.post(f"{self.base_url}/sendPhoto", data=data, files=files)
                return res.status_code == 200
        except Exception as e:
            logger.error(f"Error sending Telegram photo: {e}")
            return False

    def send_chat_action(self, chat_id: int | str, action: str = "typing") -> bool:
        """Set typing/uploading status in Telegram chat."""
        if not self.is_configured:
            return True

        try:
            with httpx.Client(timeout=5.0) as client:
                res = client.post(
                    f"{self.base_url}/sendChatAction",
                    json={"chat_id": chat_id, "action": action}
                )
                return res.status_code == 200
        except Exception:
            return False
