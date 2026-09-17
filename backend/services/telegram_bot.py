import base64
import io
import logging
from typing import List, Optional
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

    @staticmethod
    def _chunk_text(text: str, max_chars: int = 4000) -> List[str]:
        """Split text into chunks not exceeding max_chars, preserving paragraphs."""
        if not text or len(text) <= max_chars:
            return [text] if text else []

        chunks: List[str] = []
        current_chunk: List[str] = []
        current_len = 0

        for line in text.split("\n"):
            line_len = len(line) + 1  # includes newline
            if current_len + line_len > max_chars and current_chunk:
                chunks.append("\n".join(current_chunk))
                current_chunk = []
                current_len = 0

            # If a single line itself exceeds max_chars, slice it
            if len(line) > max_chars:
                for i in range(0, len(line), max_chars):
                    sub = line[i:i + max_chars]
                    if i + max_chars < len(line):
                        chunks.append(sub)
                    else:
                        current_chunk.append(sub)
                        current_len += len(sub)
            else:
                current_chunk.append(line)
                current_len += line_len

        if current_chunk:
            chunks.append("\n".join(current_chunk))

        return chunks

    def send_message(self, chat_id: int | str, text: str, parse_mode: str = "Markdown") -> bool:
        """
        Send text message to Telegram.
        Automatically splits messages > 4096 characters into sequential chunks.
        """
        if not self.is_configured:
            logger.info(f"[MOCK TG SEND] to {chat_id}: {text}")
            return True

        chunks = self._chunk_text(text, max_chars=4000)
        overall_success = True

        try:
            with httpx.Client(timeout=15.0) as client:
                for chunk in chunks:
                    res = client.post(
                        f"{self.base_url}/sendMessage",
                        json={"chat_id": chat_id, "text": chunk, "parse_mode": parse_mode}
                    )
                    if res.status_code != 200 and parse_mode:
                        logger.warning(f"Telegram Markdown parse failed ({res.text}), retrying with plain text.")
                        res = client.post(
                            f"{self.base_url}/sendMessage",
                            json={"chat_id": chat_id, "text": chunk}
                        )
                    if res.status_code != 200:
                        overall_success = False
                        logger.error(f"Failed to deliver message chunk to {chat_id}: {res.text}")
                return overall_success
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
