import streamlit as st
import pandas as pd
from utils.api_client import APIClient

st.set_page_config(page_title="Управление каналами", page_icon="⚙️", layout="wide")
st.title("⚙️ Управление списком отслеживаемых каналов")
st.caption("Добавляйте и удаляйте каналы конкурентов для автоматического ежедневного мониторинга и сбора метрик.")

client = APIClient()

# Form to add a new channel
st.subheader("➕ Добавить канал в мониторинг")
with st.form("add_channel_form"):
    col1, col2 = st.columns([3, 1])
    with col1:
        channel_input = st.text_input(
            "Handle или ссылка на YouTube-канал",
            value="@GoogleCloud",
            placeholder="@MKBHD, @veritasium или ID канала"
        )
    with col2:
        max_videos = st.number_input("Начальный срез видео", min_value=5, max_value=50, value=10)

    submitted = st.form_submit_button("Зарегистрировать и синхронизировать")

if submitted:
    if not channel_input.strip():
        st.error("Укажите валидный handle или ID канала.")
    else:
        with st.spinner(f"Валидация и подключение канала {channel_input}..."):
            result = client.add_competitor(channel_input.strip())
            if result.get("status") == "REGISTERED":
                st.success(f"Канал **{result.get('title')}** успешно добавлен в реестр BigQuery!")
                st.info(f"Подписчиков: {result.get('subscriber_count', 0):,} | Просмотров: {result.get('view_count', 0):,}")
                st.rerun()
            else:
                st.error(f"Не удалось добавить канал: {result.get('message', 'Ошибка валидации')}")

st.markdown("---")

# Display current registered channels
st.subheader("📋 Зарегистрированные каналы")
channels = client.get_channels()
if channels:
    df = pd.DataFrame(channels)
    column_mapping = {
        "title": "Название канала",
        "custom_url": "Handle / Ссылка",
        "subscriber_count": "Подписчики",
        "view_count": "Просмотры",
        "video_count": "Всего видео",
        "country": "Страна"
    }
    avail = [c for c in column_mapping.keys() if c in df.columns]
    df_display = df[avail].rename(columns=column_mapping)
    st.dataframe(df_display, use_container_width=True)

    # Section to delete a channel
    st.markdown("---")
    st.subheader("🗑️ Удалить канал из мониторинга")
    channel_options = {
        f"{c.get('title')} ({c.get('custom_url') or c.get('channel_id')})": c.get("channel_id")
        for c in channels
    }
    selected_name = st.selectbox("Выберите канал для удаления:", list(channel_options.keys()))
    selected_id = channel_options[selected_name]

    if st.button("❌ Удалить выбранный канал", type="secondary"):
        with st.spinner(f"Удаление канала {selected_name}..."):
            del_result = client.delete_competitor(selected_id)
            if del_result.get("status") == "DELETED":
                st.success(f"Канал **{selected_name}** успешно удален из BigQuery!")
                st.rerun()
            else:
                st.error(f"Ошибка удаления: {del_result.get('message')}")
else:
    st.info("Реестр каналов пуст. Зарегистрируйте свой первый канал выше.")

# -------------------------------------------------------------
# Section: Telegram Bot Users & Access Control
# -------------------------------------------------------------
st.markdown("---")
st.subheader("👥 Пользователи Telegram-бота (Доступ и безопасность)")
st.caption("Список клиентов, подключившихся к Telegram-боту, и статус их авторизации (Whitelist).")

subscribers = client.get_telegram_subscribers()
if subscribers:
    df_subs = pd.DataFrame(subscribers)
    if "is_allowed" in df_subs.columns:
        df_subs["Статус доступа"] = df_subs["is_allowed"].apply(lambda x: "🟢 Разрешен" if x else "⛔ Ограничен")
    else:
        df_subs["Статус доступа"] = "🟢 Разрешен"

    if "is_active" in df_subs.columns:
        df_subs["Дайджест"] = df_subs["is_active"].apply(lambda x: "🔔 Подписан" if x else "🔕 Отключен")

    col_sub_mapping = {
        "first_name": "Имя",
        "username": "Telegram Username",
        "chat_id": "Telegram Chat ID",
        "updated_at": "Последняя активность"
    }
    cols_to_use = ["Статус доступа", "first_name", "username", "chat_id", "Дайджест", "updated_at"]
    existing_cols = [c for c in cols_to_use if c in df_subs.columns]
    df_subs_display = df_subs[existing_cols].rename(columns=col_sub_mapping)
    st.dataframe(df_subs_display, use_container_width=True)
else:
    st.info("Пока нет зарегистрированных пользователей в Telegram-боте.")
