import streamlit as st
import pandas as pd
from utils.api_client import APIClient

st.set_page_config(page_title="Управление конкурентами", page_icon="⚙️", layout="wide")
st.title("⚙️ Управление списком отслеживаемых каналов")
st.caption("Добавляйте каналы конкурентов для автоматического ежедневного мониторинга и сбора метрик.")

client = APIClient()

# Form to add a new channel
st.subheader("➕ Добавить канал в мониторинг")
with st.form("add_channel_form"):
    col1, col2 = st.columns([3, 1])
    with col1:
        channel_input = st.text_input(
            "Handle или ссылка на YouTube канал",
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
            else:
                st.error(f"Не удалось добавить канал: {result.get('message', 'Ошибка валидации')}")

st.markdown("---")

# Display current registered channels
st.subheader("📋 Зарегистрированные каналы")
channels = client.get_channels()
if channels:
    df = pd.DataFrame(channels)
    cols = ["title", "custom_url", "subscriber_count", "view_count", "video_count", "country"]
    avail = [c for c in cols if c in df.columns]
    st.dataframe(df[avail], use_container_width=True)
else:
    st.info("Реестр каналов пуст. Зарегистрируйте свой первый канал выше.")
