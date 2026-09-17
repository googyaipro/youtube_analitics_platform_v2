import logging
from typing import Any, Dict
from fastapi import APIRouter, HTTPException, Request

from backend.prompts import load_prompt
from backend.services.agent_orchestrator import AgentOrchestrator
from backend.services.firestore_cache import FirestoreCache
from backend.services.telegram_bot import TelegramBotService
from config.settings import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tasks", tags=["Cloud Tasks Workers"])

settings = get_settings()
agent = AgentOrchestrator()
bot = TelegramBotService()
cache = FirestoreCache()


def handle_telegram_update_internal(update: Dict[str, Any]):
    """Internal processing logic for Telegram update."""
    message = update.get("message") or update.get("edited_message")
    if not message:
        return

    chat_id = str(message.get("chat", {}).get("id"))
    text = message.get("text", "")
    if not chat_id or not text:
        return

    from_user = message.get("from", {})
    username = (from_user.get("username") or "").lower().strip()
    first_name = from_user.get("first_name", "User")

    # 1. Access Control (Whitelist)
    allowed_tokens = set()
    if settings.TELEGRAM_ADMIN_CHAT_ID:
        allowed_tokens.add(str(settings.TELEGRAM_ADMIN_CHAT_ID).strip())
    if settings.TELEGRAM_ALLOWED_USERS:
        import re
        for u in re.split(r"[,;:\s]+", settings.TELEGRAM_ALLOWED_USERS):
            token = u.strip().lstrip("@").lower()
            if token:
                allowed_tokens.add(token)

    is_allowed = True
    if allowed_tokens:
        is_allowed = (chat_id in allowed_tokens) or (username in allowed_tokens)

    # Register user in Firestore with their authorization status
    cache.register_telegram_subscriber(chat_id, from_user, is_allowed=is_allowed)

    if not is_allowed:
        logger.warning(f"Unauthorized access attempt to Telegram bot by {first_name} (@{username}, ID: {chat_id})")
        bot.send_message(
            chat_id,
            f"⛔ **Доступ ограничен**\n\n"
            f"Этот бот является закрытой аналитической платформой компании.\n"
            f"Ваш Telegram ID: `{chat_id}`\n\n"
            f"Для получения доступа обратитесь к администратору."
        )
        # Notify admin of unauthorized attempt
        if settings.TELEGRAM_ADMIN_CHAT_ID and str(settings.TELEGRAM_ADMIN_CHAT_ID) != chat_id:
            bot.send_message(
                settings.TELEGRAM_ADMIN_CHAT_ID,
                f"🔔 **Попытка доступа к боту!**\n"
                f"• Пользователь: **{first_name}** (@{username or 'без_юзернейма'})\n"
                f"• ID: `{chat_id}`\n"
                f"• Сообщение: _{text}_"
            )
        return

    # Parse command and arguments
    clean_text = text.strip()
    first_word = clean_text.split()[0].lower() if clean_text else ""
    # Strip @bot_username if sent as /command@botname (standard Telegram client behavior in chats)
    cmd = first_word.split("@")[0] if first_word.startswith("/") else ""

    # Handle /users or /user command (Admin only)
    if cmd in ("/users", "/user"):
        if settings.TELEGRAM_ADMIN_CHAT_ID and chat_id != str(settings.TELEGRAM_ADMIN_CHAT_ID):
            bot.send_message(chat_id, "⚠️ Команда `/users` доступна только администратору бота.")
            return
        subscribers = cache.get_all_subscribers()
        if not subscribers:
            bot.send_message(chat_id, "ℹ️ Список пользователей пуст.")
            return
        lines = ["👥 **Зарегистрированные пользователи бота:**\n"]
        for idx, u in enumerate(subscribers, 1):
            status_icon = "🟢" if u.get("is_allowed", True) else "⛔"
            uname = f"@{u.get('username')}" if u.get("username") else "без username"
            name = u.get("first_name", "Не указано")
            lines.append(f"{idx}. {status_icon} **{name}** ({uname}) — ID: `{u.get('chat_id')}`")
        bot.send_message(chat_id, "\n".join(lines))
        return

    # Handle /start and /help commands
    if cmd in ("/start", "/help"):
        welcome_msg = load_prompt("telegram_welcome.txt")
        bot.send_message(chat_id, welcome_msg)
        return

    # Handle /list and /channels commands
    if cmd in ("/list", "/channels"):
        channels = agent.bq.get_channels()
        if not channels:
            bot.send_message(chat_id, "ℹ️ Список отслеживаемых каналов пуст. Добавьте канал командой: `/add @handle`")
        else:
            lines = ["📋 **Отслеживаемые каналы:**\n"]
            for idx, c in enumerate(channels, 1):
                lines.append(f"{idx}. **{c.get('title')}** ({c.get('custom_url') or c.get('channel_id')}) — {c.get('subscriber_count', 0):,} subs")
            bot.send_message(chat_id, "\n".join(lines))
        return

    # Handle /add command
    if cmd == "/add":
        parts = clean_text.split(maxsplit=1)
        if len(parts) < 2:
            bot.send_message(chat_id, "ℹ️ Укажите канал для добавления. Пример:\n`/add @juliangoldieseo`")
            return
        handle = parts[1].strip()
        bot.send_chat_action(chat_id, "typing")
        bot.send_message(chat_id, f"⏳ Добавляю канал *{handle}* в мониторинг...")
        ch = agent.yt.get_channel(handle)
        if ch:
            agent.bq.insert_channel(ch)
            vids = agent.yt.get_channel_uploads(ch.channel_id, max_results=10)
            if vids:
                agent.bq.insert_videos(vids)
            bot.send_message(
                chat_id,
                f"✅ Канал **{ch.snippet.title}** успешно добавлен!\n\n"
                f"• Подписчиков: **{ch.statistics.subscriber_count:,}**\n"
                f"• Суммарно просмотров: **{ch.statistics.view_count:,}**\n"
                f"• Загружено роликов: **{ch.statistics.video_count:,}**"
            )
        else:
            bot.send_message(chat_id, f"❌ Канал '{handle}' не найден в YouTube.")
        return

    # Handle /delete or /remove command
    if cmd in ("/delete", "/remove"):
        parts = clean_text.split(maxsplit=1)
        if len(parts) < 2:
            bot.send_message(chat_id, "ℹ️ Укажите канал для удаления. Пример:\n`/delete @handle`")
            return
        target = parts[1].strip()
        channels = agent.bq.get_channels()
        target_id = None
        target_title = target
        for c in channels:
            if target.lower() in (c.get("title", "").lower(), c.get("custom_url", "").lower(), c.get("channel_id", "").lower()):
                target_id = c.get("channel_id")
                target_title = c.get("title")
                break
        if target_id:
            agent.bq.delete_channel(target_id)
            bot.send_message(chat_id, f"🗑️ Канал **{target_title}** успешно удален из мониторинга.")
        else:
            bot.send_message(chat_id, f"Канал '{target}' не найден в вашем списке отслеживаемых каналов.")
        return

    # Handle /explain command or natural question about video success
    is_explain_query = (
        cmd in ("/explain", "/why", "/breakdown")
        or any(phrase in text.lower() for phrase in ["почему выстрелил", "почему ролик", "разбор видео", "факторы успеха", "почему в топе", "почему на первом месте", "разбор ролика"])
    )

    if is_explain_query:
        target_query = ""
        if cmd:
            parts = clean_text.split(maxsplit=1)
            target_query = parts[1].strip() if len(parts) > 1 else "1"
        else:
            target_query = clean_text

        bot.send_chat_action(chat_id, "typing")
        bot.send_message(chat_id, "🔍 *Анализирую факторы успеха ролика через Gemini 3.5 Flash...*")

        video = agent.bq.get_video_by_id_or_title(target_query)
        if not video:
            bot.send_message(
                chat_id,
                "❌ Не удалось найти указанный ролик в базе данных.\n"
                "Попробуйте передать команду с номером в топе, например: `/explain 1` или `/explain GPT-6`."
            )
            return

        from backend.services.gemini_service import GeminiService
        gemini = GeminiService()
        explanation = gemini.explain_video_success(video)

        score = float(video.get("outlier_score") or 1.0)
        vph = float(video.get("velocity_vph") or 0.0)
        er = float(video.get("engagement_rate_pct") or 0.0)
        views = video.get("view_count", 0)
        avg_views = int(video.get("channel_avg_views") or views)
        badges_str = " ".join([f"`{b}`" for b in video.get("badges", [])])

        msg = (
            f"🎯 **Разбор факторов успеха ролика**\n\n"
            f"🎬 **[{video.get('title')}](https://www.youtube.com/watch?v={video.get('video_id')})**\n"
            f"📺 Канал: **{video.get('channel_title')}**\n"
            f"{badges_str}\n\n"
            f"📊 **Ключевые метрики:**\n"
            f"• 👁️ Просмотры: **{views:,}** (в **{score}x** выше нормы канала: {avg_views:,})\n"
            f"• ⚡ Скорость: **{vph} просм/час**\n"
            f"• 💬 Вовлеченность (ER): **{er:.2f}%** (👍 {video.get('like_count', 0):,} • 💬 {video.get('comment_count', 0):,})\n\n"
            f"💡 **Вердикт AI (Gemini 3.5 Flash):**\n"
            f"{explanation.get('verdict')}\n\n"
            f"🪝 **Крючки темы и заголовка:**\n"
            f"{explanation.get('hook_analysis')}\n\n"
            f"🔥 **Оседланный тренд:**\n"
            f"{explanation.get('trend_alignment')}\n\n"
            f"🛠️ **Как повторить успех:**\n"
            f"_{explanation.get('actionable_takeaway')}_"
        )
        bot.send_message(chat_id, msg)
        return

    # Reject unknown slash commands
    if cmd:
        bot.send_message(
            chat_id,
            f"⚠️ Неизвестная команда `{cmd}`.\n\n"
            f"Используйте `/help` для просмотра списка команд или отправьте текстовый запрос (например: *Сравни последние видео @juliangoldieseo*)."
        )
        return

    # Send typing status
    bot.send_chat_action(chat_id, "upload_photo")
    bot.send_message(chat_id, f"⏳ *Анализирую данные по запросу:* _{text}_ ...")

    try:
        # Run agent orchestrator (returns Matplotlib PNG + text summary)
        result = agent.process_query(user_text=text, output_format="matplotlib")

        # 1. Send Matplotlib chart if generated
        png_base64 = result.get("png_base64")
        if png_base64:
            caption = f"📊 График показателей: **{result.get('channel_title')}**"
            bot.send_photo(chat_id=chat_id, png_base64=png_base64, caption=caption)

        # 2. Send text summary & key findings
        findings_bullets = "\n".join([f"• {f}" for f in result.get("key_findings", [])])
        summary_message = (
            f"{result.get('summary_text')}\n\n"
            f"**Ключевые инсайты:**\n{findings_bullets}"
        )
        bot.send_message(chat_id=chat_id, text=summary_message)

    except Exception as e:
        logger.error(f"Error processing Telegram task: {e}", exc_info=True)
        bot.send_message(
            chat_id=chat_id,
            text=f"⚠️ Произошла ошибка при анализе: {str(e)}"
        )


@router.post("/process-telegram-message")
async def process_telegram_message(request: Request):
    """
    Dedicated worker endpoint triggered by Google Cloud Tasks.
    Executes with full dedicated CPU and automatic retries.
    """
    update_data = await request.json()
    logger.info("Executing Cloud Task: process-telegram-message")
    handle_telegram_update_internal(update_data)
    return {"status": "SUCCESS"}
