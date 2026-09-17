import streamlit as st
import pandas as pd
import plotly.express as px
from utils.api_client import APIClient

st.set_page_config(page_title="Динамика конкурентов", page_icon="📈", layout="wide")
st.title("📈 Мониторинг конкурентов: Динамика и лидерборды")
st.caption("Быстрые запросы к хранилищу BigQuery (v_latest_channel_stats) без расхода квот YouTube API.")

client = APIClient()
channels = client.get_channels()

if not channels:
    st.info("В базе данных пока нет каналов. Добавьте первый канал во вкладке **⚙️ Управление каналами**.")
else:
    df_channels = pd.DataFrame(channels)

    # Top metrics row
    st.subheader("🏆 Лидерборд каналов")
    col1, col2 = st.columns(2)

    with col1:
        fig_subs = px.bar(
            df_channels.sort_values(by="subscriber_count", ascending=False),
            x="title",
            y="subscriber_count",
            color="subscriber_count",
            title="Подписчики по каналам",
            labels={"title": "Канал", "subscriber_count": "Подписчики"},
            text_auto=True,
            color_continuous_scale="Blues"
        )
        st.plotly_chart(fig_subs, use_container_width=True)

    with col2:
        fig_views = px.bar(
            df_channels.sort_values(by="view_count", ascending=False),
            x="title",
            y="view_count",
            color="view_count",
            title="Суммарные просмотры",
            labels={"title": "Канал", "view_count": "Просмотры"},
            text_auto=True,
            color_continuous_scale="Viridis"
        )
        st.plotly_chart(fig_views, use_container_width=True)

    st.markdown("---")
    st.subheader("📋 Сводная таблица каналов")
    df_channels["channel_url"] = df_channels.apply(
        lambda r: f"https://www.youtube.com/{r['custom_url']}" if r.get("custom_url") and str(r["custom_url"]).startswith("@") else f"https://www.youtube.com/channel/{r['channel_id']}",
        axis=1
    )
    column_mapping = {
        "title": "Название канала",
        "custom_url": "Handle",
        "subscriber_count": "Подписчики",
        "view_count": "Просмотры",
        "video_count": "Всего видео",
        "country": "Страна",
        "channel_url": "YouTube"
    }
    cols_to_show = [c for c in column_mapping.keys() if c in df_channels.columns]
    df_display = df_channels[cols_to_show].rename(columns=column_mapping)
    st.dataframe(
        df_display,
        column_config={
            "YouTube": st.column_config.LinkColumn("YouTube", display_text="🔗 Открыть канал"),
            "Подписчики": st.column_config.NumberColumn("Подписчики", format="%d"),
            "Просмотры": st.column_config.NumberColumn("Просмотры", format="%d"),
            "Всего видео": st.column_config.NumberColumn("Всего видео", format="%d"),
        },
        hide_index=True,
        use_container_width=True
    )
