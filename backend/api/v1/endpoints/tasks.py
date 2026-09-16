import logging
from typing import Any, Dict
from fastapi import APIRouter, HTTPException, Request

from backend.services.agent_orchestrator import AgentOrchestrator
from backend.services.firestore_cache import FirestoreCache
from backend.services.telegram_bot import TelegramBotService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tasks", tags=["Cloud Tasks Workers"])

agent = AgentOrchestrator()
bot = TelegramBotService()
cache = FirestoreCache()


def handle_telegram_update_internal(update: Dict[str, Any]):
    """Internal processing logic for Telegram update."""
    message = update.get("message") or update.get("edited_message")
    if not message:
        return

    chat_id = message.get("chat", {}).get("id")
    text = message.get("text", "")
    if not chat_id or not text:
        return

    # Register user as active subscriber for daily morning digests
    from_user = message.get("from", {})
    cache.register_telegram_subscriber(chat_id, from_user)

    # Handle /start command
    if text.strip() == "/start":
        welcome_msg = (
            "👋 **Добро пожаловать в YouTube Analytics Platform!**\n\n"
            "Я помогу проанализировать каналы конкурентов, сравнить просмотры и динамику.\n\n"
            "**Команды управления каналами:**\n"
            "• `/list` — показать список отслеживаемых каналов\n"
            "• `/add @handle` — добавить канал в мониторинг\n"
            "• `/delete @handle` — удалить канал из мониторинга\n\n"
            "**Примеры аналитических запросов:**\n"
            "• *Сравни просмотры последних видео @MKBHD*\n"
            "• *Покажи аналитику канала @GoogleCloud*\n"
            "• *Какая вовлеченность у последних роликов MrBeast?*"
        )
        bot.send_message(chat_id, welcome_msg)
        return

    # Handle /list command
    if text.strip() == "/list":
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
    if text.startswith("/add "):
        handle = text.replace("/add ", "").strip()
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

    # Handle /delete command
    if text.startswith("/delete ") or text.startswith("/remove "):
        target = text.split(maxsplit=1)[1].strip()
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
