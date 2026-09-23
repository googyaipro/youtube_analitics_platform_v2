import streamlit as st
import pandas as pd
import plotly.express as px
from dashboard.utils.api_client import get_api_client
from dashboard.utils.auth_ui import require_auth
from dashboard.utils.i18n import t

st.set_page_config(page_title="Динамика и Лидерборд", page_icon="📈", layout="wide")

user = require_auth()
client = get_api_client()

active_set_id = user.get("active_set_id")

st.title("📈 Мониторинг конкурентов: Динамика и лидерборды")
st.caption("Анализ темпов роста, вовлеченности и распределения виральности в активном наборе каналов.")

channels = client.get_channels(set_id=active_set_id)
videos = client.get_videos(set_id=active_set_id, limit=100)

if not channels:
    st.info(t("no_channels"))
else:
    df_channels = pd.DataFrame(channels)

    # 1. Channels leaderboard
    st.subheader("🏆 Лидерборд каналов в наборе")
    col1, col2 = st.columns(2)

    with col1:
        fig_subs = px.bar(
            df_channels.sort_values(by="subscriber_count", ascending=False),
            x="title",
            y="subscriber_count",
            color="subscriber_count",
            title="Подписчики по каналам",
            labels={"title": "Канал", "subscriber_count": "Подписчики"},
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
            color_continuous_scale="Teal"
        )
        st.plotly_chart(fig_views, use_container_width=True)

    # 2. Virality Matrix (Scatter plot)
    if videos:
        st.markdown("---")
        st.subheader("🎯 Матрица виральности: Просмотры vs Множитель нормы (Outlier Score)")
        df_v = pd.DataFrame(videos)
        
        fig_scatter = px.scatter(
            df_v,
            x="view_count",
            y="outlier_score",
            size="velocity_vph",
            color="channel_title",
            hover_name="title",
            labels={
                "view_count": "Просмотры",
                "outlier_score": "Множитель к средней норме автора",
                "velocity_vph": "Скорость (VPH)",
                "channel_title": "Канал"
            },
            title="Видео с наивысшим отклонением от нормы (Размер точки = Скорость набора VPH)"
        )
        fig_scatter.add_hline(y=1.8, line_dash="dash", line_color="red", annotation_text="Порог вирального хита (1.8x)")
        st.plotly_chart(fig_scatter, use_container_width=True)

    # 3. Channels Table
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
