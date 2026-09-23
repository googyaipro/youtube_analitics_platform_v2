import logging
from typing import Any, Dict, List, Optional
import httpx
from sqlalchemy.orm import Session

from backend.core.security import decrypt_secret
from backend.models.user import User
from backend.models.channel_set import ChannelSet
from backend.models.channel import Channel
from backend.services.analytics_service import AnalyticsService
from backend.services.gemini_service import GeminiService
from config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class TelegramService:
    @staticmethod
    def _chunk_text(text: str, max_chars: int = 4000) -> List[str]:
        """Split text into chunks not exceeding max_chars, preserving paragraphs."""
        if not text or len(text) <= max_chars:
            return [text] if text else []

        chunks: List[str] = []
        current_chunk: List[str] = []
        current_len = 0

        for line in text.split("\n"):
            line_len = len(line) + 1
            if current_len + line_len > max_chars and current_chunk:
                chunks.append("\n".join(current_chunk))
                current_chunk = []
                current_len = 0

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

    @classmethod
    def send_message(cls, chat_id: int | str, text: str, parse_mode: str = "Markdown") -> bool:
        """Send message to Telegram with auto-splitting for long messages and plain-text fallback."""
        bot_token = settings.TELEGRAM_BOT_TOKEN
        if not bot_token or " " in bot_token:
            logger.info(f"[MOCK TG SEND] to {chat_id}: {text[:100]}...")
            return True

        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        chunks = cls._chunk_text(text, max_chars=4000)
        overall_success = True

        try:
            with httpx.Client(timeout=15.0) as client:
                for chunk in chunks:
                    res = client.post(url, json={"chat_id": chat_id, "text": chunk, "parse_mode": parse_mode})
                    if res.status_code != 200 and parse_mode:
                        # Fallback without markdown if special chars cause Telegram parse error
                        res = client.post(url, json={"chat_id": chat_id, "text": chunk})
                    if res.status_code != 200:
                        overall_success = False
                        logger.error(f"Telegram error delivering chunk to {chat_id}: {res.text}")
                return overall_success
        except Exception as e:
            logger.error(f"Network error sending telegram message: {e}")
            return False

    @classmethod
    def get_bot_info(cls) -> Optional[Dict[str, Any]]:
        """Fetch bot metadata from Telegram getMe."""
        bot_token = settings.TELEGRAM_BOT_TOKEN
        if not bot_token or " " in bot_token:
            return None
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.get(f"https://api.telegram.org/bot{bot_token}/getMe")
                if res.status_code == 200 and res.json().get("ok"):
                    return res.json().get("result")
                logger.warning(f"Telegram getMe failed ({res.status_code}): {res.text}")
        except Exception as e:
            logger.error(f"Error fetching Telegram getMe: {e}")
        return None

    @classmethod
    def get_webhook_info(cls) -> Optional[Dict[str, Any]]:
        """Fetch current webhook registration status from Telegram getWebhookInfo."""
        bot_token = settings.TELEGRAM_BOT_TOKEN
        if not bot_token or " " in bot_token:
            return None
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.get(f"https://api.telegram.org/bot{bot_token}/getWebhookInfo")
                if res.status_code == 200 and res.json().get("ok"):
                    return res.json().get("result")
                logger.warning(f"Telegram getWebhookInfo failed ({res.status_code}): {res.text}")
        except Exception as e:
            logger.error(f"Error fetching Telegram getWebhookInfo: {e}")
        return None

    @classmethod
    def register_webhook(cls) -> Dict[str, Any]:
        """Automatically register webhook URL and bot commands with Telegram."""
        bot_token = settings.TELEGRAM_BOT_TOKEN
        if not bot_token or " " in bot_token:
            return {"ok": False, "description": "TELEGRAM_BOT_TOKEN is not configured"}

        webhook_url = f"https://{settings.DOKPLOY_API_DOMAIN}/api/v1/telegram/webhook"
        tg_url = f"https://api.telegram.org/bot{bot_token}/setWebhook"
        params: Dict[str, Any] = {
            "url": webhook_url,
            "drop_pending_updates": False
        }
        if settings.TELEGRAM_WEBHOOK_SECRET:
            params["secret_token"] = settings.TELEGRAM_WEBHOOK_SECRET

        result = {"ok": False}
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.post(tg_url, json=params)
                result = res.json()
                logger.info(f"Telegram setWebhook result: {result}")

                # Register bot commands menu
                commands = [
                    {"command": "top", "description": "Top 10 videos of active set"},
                    {"command": "sets", "description": "Your channel sets & schedules"},
                    {"command": "explain", "description": "AI analysis of video (e.g. /explain 1)"},
                    {"command": "lang", "description": "Change language (ru, en, de, fi, ka)"},
                    {"command": "status", "description": "Check API keys and schedule"},
                    {"command": "help", "description": "Commands help"}
                ]
                client.post(f"https://api.telegram.org/bot{bot_token}/setMyCommands", json={"commands": commands})
        except Exception as e:
            logger.error(f"Error registering Telegram webhook: {e}")
            result = {"ok": False, "description": str(e)}

        return result

    @classmethod
    def handle_webhook_update(cls, db: Session, update: Dict[str, Any]) -> bool:
        """Process incoming Telegram message, command, or deep-linking binding."""
        message = update.get("message", {})
        if not message:
            return True

        chat_id = str(message.get("chat", {}).get("id"))
        text = message.get("text", "").strip()
        tg_lang = message.get("from", {}).get("language_code", "ru")

        # 1. Check if user is already linked
        user = db.query(User).filter(User.telegram_chat_id == chat_id).first()

        # 2. Check for binding code (either in /start <token> or sent directly as code)
        link_code_candidate = None
        if text.startswith("/start"):
            parts = text.split()
            if len(parts) > 1:
                link_code_candidate = parts[1].strip()

        if not link_code_candidate:
            for token in text.split():
                clean = token.strip()
                if clean and db.query(User).filter(User.telegram_link_code == clean).first():
                    link_code_candidate = clean
                    break

        dash_url = settings.DASHBOARD_URL.rstrip("/")

        if link_code_candidate:
            target_user = db.query(User).filter(User.telegram_link_code == link_code_candidate).first()
            if target_user:
                target_user.telegram_chat_id = chat_id
                target_user.telegram_link_code = None
                if not target_user.language and tg_lang in ("ru", "en", "de", "fi", "ka"):
                    target_user.language = tg_lang
                db.commit()
                cls.send_message(
                    chat_id,
                    f"🎉 **Аккаунт успешно привязан!**\n\nДобро пожаловать, **{target_user.email}**!\nТеперь вам будут приходить персональные дайджесты по вашим наборам каналов с платформы [{dash_url}]({dash_url}).\n\nИспользуйте команду /help для списка возможностей."
                )
                return True
            else:
                cls.send_message(chat_id, f"⚠️ Код привязки устарел или недействителен. Сгенерируйте новую ссылку в личном кабинете на {dash_url}.")
                return True

        # If user is not yet bound
        if not user:
            if text.startswith("/start"):
                cls.send_message(
                    chat_id,
                    f"👋 Привет! Чтобы связать этого бота с вашим аккаунтом на платформе аналитики:\n1. Зайдите в профиль на **{dash_url}**\n2. Нажмите кнопку **«Привязать Telegram»**\n3. Перейдите по ссылке или отправьте полученный 16-значный код прямо сюда в чат."
                )
                return True

            cls.send_message(
                chat_id,
                f"🔒 Ваш Telegram-аккаунт еще не привязан к личному кабинету.\nАвторизуйтесь на **{dash_url}**, нажмите «Привязать Telegram» в настройках профиля и отправьте сюда 16-значный код привязки."
            )
            return True

        # User is authenticated! Handle commands:
        if text.startswith("/start"):
            cls.send_message(chat_id, f"👋 С возвращением, **{user.email}**! Используйте /sets для выбора набора или /top для просмотра лидеров.")
            return True

        # User is authenticated! Handle commands:
        if text == "/help":
            cls.send_message(
                chat_id,
                "🤖 **Доступные команды:**\n"
                "• /digest — Свежий исполнительный AI-дайджест ниши\n"
                "• /top — Топ-10 роликов текущего набора с виральными бейджами\n"
                "• /explain <номер_в_топе> — Глубокий разбор факторов успеха видео через Gemini\n"
                "• /sets — Просмотр и выбор активного набора каналов\n"
                "• /lang <ru|en|de|fi|ka> — Смена языка аналитики\n"
                "• /status — Проверка статуса API-ключей и расписания\n\n"
                f"🌐 Личный кабинет: [{dash_url}]({dash_url})"
            )
            return True

        elif text in ("/digest", "дайджест", "digest"):
            active_set_id = user.active_set_id
            if not active_set_id:
                first_set = db.query(ChannelSet).filter(ChannelSet.user_id == user.id).first()
                if first_set:
                    user.active_set_id = first_set.id
                    db.commit()
                    active_set_id = first_set.id

            if not active_set_id:
                cls.send_message(chat_id, f"❌ У вас нет активных наборов каналов. Создайте набор на {dash_url}.")
                return True

            active_set = db.query(ChannelSet).filter(ChannelSet.id == active_set_id).first()
            cls.send_message(chat_id, f"⏳ Составляю executive AI-дайджест по набору «{active_set.name}»...")

            enriched_videos = AnalyticsService.get_set_enriched_videos(db, user.id, active_set_id, limit=15)
            channels = db.query(Channel).filter(Channel.user_id == user.id, Channel.set_id == active_set_id).all()
            channels_summary = [{"title": c.title, "subscriber_count": c.subscriber_count} for c in channels]

            anomalies = []
            for v in enriched_videos:
                if v.get("outlier_score", 1.0) >= 1.8:
                    anomalies.append(f"Канал {v.get('channel_title')}: «{v.get('title')}» — {v.get('view_count', 0):,} просмотров ({v.get('outlier_score')}x)")

            gemini_key = decrypt_secret(user.gemini_api_key_encrypted)
            digest_text = GeminiService.generate_daily_digest(
                set_name=active_set.name,
                channels_summary=channels_summary,
                top_videos=enriched_videos,
                anomalies=anomalies,
                target_language=user.language or "ru",
                gemini_api_key=gemini_key
            )
            cls.send_message(chat_id, digest_text)
            return True

        elif text == "/sets":
            sets = db.query(ChannelSet).filter(ChannelSet.user_id == user.id).all()
            if not sets:
                cls.send_message(chat_id, f"У вас пока нет созданных наборов каналов. Создайте первый набор в дашборде на {dash_url}.")
                return True
            lines = ["📁 **Ваши наборы каналов:**"]
            for idx, s in enumerate(sets, 1):
                active_mark = " 🟢 (Активен)" if s.id == user.active_set_id else ""
                lines.append(f"{idx}. **{s.name}**{active_mark} — расписание: {s.schedule_time} ({s.schedule_timezone})")
            lines.append("\nЧтобы выбрать набор, отправьте команду: `/set <номер>` (например: `/set 1`)")
            cls.send_message(chat_id, "\n".join(lines))
            return True

        elif text.startswith("/set "):
            arg = text.replace("/set ", "").strip()
            sets = db.query(ChannelSet).filter(ChannelSet.user_id == user.id).all()
            target_set = None
            if arg.isdigit():
                idx = int(arg) - 1
                if 0 <= idx < len(sets):
                    target_set = sets[idx]
            else:
                for s in sets:
                    if s.name.lower() == arg.lower():
                        target_set = s
                        break

            if target_set:
                user.active_set_id = target_set.id
                db.commit()
                cls.send_message(chat_id, f"✅ Активным выбран набор: **«{target_set.name}»**! Теперь команды /top и дайджесты работают по нему.")
            else:
                cls.send_message(chat_id, "❌ Набор не найден. Используйте /sets для просмотра номеров наборов.")
            return True

        elif text.startswith("/lang"):
            parts = text.split()
            if len(parts) > 1 and parts[1].lower() in ("ru", "en", "de", "fi", "ka"):
                user.language = parts[1].lower()
                db.commit()
                cls.send_message(chat_id, f"🌐 Язык интерфейса и отчетов успешно изменен на: **{user.language}**!")
            else:
                cls.send_message(chat_id, "Укажите язык: `/lang ru`, `/lang en`, `/lang de`, `/lang fi` или `/lang ka`.")
            return True

        elif text == "/top":
            active_set_id = user.active_set_id
            if not active_set_id:
                first_set = db.query(ChannelSet).filter(ChannelSet.user_id == user.id).first()
                if first_set:
                    user.active_set_id = first_set.id
                    db.commit()
                    active_set_id = first_set.id

            if not active_set_id:
                cls.send_message(chat_id, f"❌ У вас нет активных наборов каналов. Создайте набор на {dash_url}.")
                return True

            active_set = db.query(ChannelSet).filter(ChannelSet.id == active_set_id).first()
            videos = AnalyticsService.get_set_enriched_videos(db, user.id, active_set_id, limit=10)
            if not videos:
                cls.send_message(chat_id, f"В наборе «{active_set.name}» пока нет собранных роликов. Добавьте каналы на {dash_url} или запустите синхронизацию.")
                return True

            lines = [f"🏆 **Топ видео набора «{active_set.name}»:**\n"]
            for idx, v in enumerate(videos, 1):
                badges_str = " ".join(v.get("badges", []))
                lines.append(f"**#{idx}** {badges_str}\n• **«{v.get('title')}»**\n  Канал: {v.get('channel_title')} | 👁 {v.get('view_count'):,} | VPH: {v.get('velocity_vph')}\n")
            lines.append("Для глубокого AI-разбора ролика отправьте: `/explain <номер>` (например: `/explain 1`)")
            cls.send_message(chat_id, "\n".join(lines))
            return True

        elif text.startswith("/explain"):
            arg = text.replace("/explain", "").strip()
            if not arg:
                cls.send_message(chat_id, "Укажите номер видео из топа. Например: `/explain 1`.")
                return True

            active_set_id = user.active_set_id
            if not active_set_id:
                cls.send_message(chat_id, "Выберите активный набор через /sets.")
                return True

            videos = AnalyticsService.get_set_enriched_videos(db, user.id, active_set_id, limit=20)
            target_video = None
            if arg.isdigit():
                idx = int(arg) - 1
                if 0 <= idx < len(videos):
                    target_video = videos[idx]

            if not target_video:
                cls.send_message(chat_id, "❌ Видео не найдено в текущем топе. Сначала вызовите /top.")
                return True

            gemini_key = decrypt_secret(user.gemini_api_key_encrypted)
            explanation = GeminiService.explain_video_success(target_video, user.language or "ru", gemini_key)

            msg = (
                f"🧠 **AI-Разбор успеха ролика (Gemini):**\n"
                f"«{target_video.get('title')}» ({target_video.get('channel_title')})\n\n"
                f"📊 **Метрики:** {target_video.get('view_count'):,} просм. | {target_video.get('outlier_score')}x от нормы | {target_video.get('velocity_vph')} VPH\n\n"
                f"🎯 **Вердикт:**\n{explanation.get('verdict')}\n\n"
                f"🎣 **Хук и заголовок:**\n{explanation.get('hook_analysis')}\n\n"
                f"🔥 **Оседланный тренд:**\n{explanation.get('trend_alignment')}\n\n"
                f"💡 **Рекомендация автору:**\n{explanation.get('actionable_takeaway')}"
            )
            cls.send_message(chat_id, msg)
            return True

        elif text == "/status":
            yt_status = "🟢 Настроен" if user.youtube_api_key_valid else "🔴 Не настроен / Не валиден"
            gemini_status = "🟢 Настроен" if user.gemini_api_key_valid else "🔴 Не настроен / Не валиден"
            active_set = db.query(ChannelSet).filter(ChannelSet.id == user.active_set_id).first() if user.active_set_id else None
            set_name = active_set.name if active_set else "Не выбран"

            cls.send_message(
                chat_id,
                f"⚙️ **Статус вашего аккаунта ({user.email}):**\n\n"
                f"• YouTube API Key: {yt_status}\n"
                f"• Gemini API Key: {gemini_status}\n"
                f"• Активный набор: **{set_name}**\n"
                f"• Язык отчетов: **{user.language}**\n\n"
                f"Управление ключами и наборами: [{dash_url}]({dash_url})"
            )
            return True

        else:
            cls.send_message(chat_id, "Неизвестная команда. Отправьте /help для списка команд.")
            return True
