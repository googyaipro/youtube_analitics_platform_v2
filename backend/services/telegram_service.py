import logging
from typing import Any, Dict, List, Optional
import httpx
from sqlalchemy.orm import Session

from backend.core.security import decrypt_secret
from backend.models.user import User
from backend.models.channel_set import ChannelSet
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

        # Command /start [token]
        if text.startswith("/start"):
            parts = text.split()
            if len(parts) > 1:
                link_code = parts[1].strip()
                target_user = db.query(User).filter(User.telegram_link_code == link_code).first()
                if target_user:
                    target_user.telegram_chat_id = chat_id
                    target_user.telegram_link_code = None
                    if not target_user.language and tg_lang in ("ru", "en", "de", "fi", "ka"):
                        target_user.language = tg_lang
                    db.commit()
                    cls.send_message(
                        chat_id,
                        f"🎉 **Аккаунт успешно привязан!**\n\nДобро пожаловать, **{target_user.email}**!\nТеперь вам будут приходить персональные дайджесты по вашим наборам каналов с сайта [yap.oxyjet.win](https://yap.oxyjet.win).\n\nИспользуйте команду /help для списка возможностей."
                    )
                    return True
                else:
                    cls.send_message(chat_id, "⚠️ Код привязки устарел или недействителен. Сгенерируйте новую ссылку в личном кабинете на yap.oxyjet.win.")
                    return True
            else:
                if user:
                    cls.send_message(chat_id, f"👋 С возвращением, **{user.email}**! Используйте /sets для выбора набора или /top для просмотра лидеров.")
                else:
                    cls.send_message(
                        chat_id,
                        "👋 Привет! Чтобы связать этого бота с вашим аккаунтом на платформе аналитики:\n1. Зайдите в профиль на **https://yap.oxyjet.win**\n2. Нажмите кнопку **«Привязать Telegram»**\n3. Перейдите по сгенерированной ссылке."
                    )
                return True

        if not user:
            cls.send_message(
                chat_id,
                "🔒 Ваш Telegram-аккаунт еще не привязан к личному кабинету.\nАвторизуйтесь на **https://yap.oxyjet.win** и нажмите «Привязать Telegram» в настройках профиля."
            )
            return True

        # User is authenticated! Handle commands:
        if text == "/help":
            cls.send_message(
                chat_id,
                "🤖 **Доступные команды:**\n"
                "• /sets — Просмотр и выбор активного набора каналов\n"
                "• /top — Топ-10 роликов текущего набора с виральными бейджами\n"
                "• /explain <номер_в_топе> — Глубокий разбор факторов успеха видео через Gemini\n"
                "• /lang <ru|en|de|fi|ka> — Смена языка аналитики\n"
                "• /status — Проверка статуса API-ключей и расписания\n\n"
                "🌐 Личный кабинет: [yap.oxyjet.win](https://yap.oxyjet.win)"
            )
            return True

        elif text == "/sets":
            sets = db.query(ChannelSet).filter(ChannelSet.user_id == user.id).all()
            if not sets:
                cls.send_message(chat_id, "У вас пока нет созданных наборов каналов. Создайте первый набор в дашборде на yap.oxyjet.win.")
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
                cls.send_message(chat_id, "❌ У вас нет активных наборов каналов. Создайте набор на yap.oxyjet.win.")
                return True

            active_set = db.query(ChannelSet).filter(ChannelSet.id == active_set_id).first()
            videos = AnalyticsService.get_set_enriched_videos(db, user.id, active_set_id, limit=10)
            if not videos:
                cls.send_message(chat_id, f"В наборе «{active_set.name}» пока нет собранных роликов. Добавьте каналы на yap.oxyjet.win или запустите синхронизацию.")
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
                f"Управление ключами и наборами: [yap.oxyjet.win](https://yap.oxyjet.win)"
            )
            return True

        else:
            cls.send_message(chat_id, "Неизвестная команда. Отправьте /help для списка команд.")
            return True
