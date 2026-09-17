import streamlit as st
import pandas as pd
import plotly.express as px
from utils.api_client import APIClient

st.set_page_config(
    page_title="YouTube Analytics Platform",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

client = APIClient()

# Header
col_head, col_btn = st.columns([4, 1])
with col_head:
    st.title("🎬 YouTube Analytics Platform")
    st.caption("Serverless-платформа аналитики каналов на базе Google Cloud (Cloud Run, BigQuery, Firestore, Vertex AI)")
with col_btn:
    st.write("")
    if st.button("🔄 Обновить данные", use_container_width=True):
        st.rerun()

# Fetch KPIs
kpis = client.get_kpis()

col1, col2, col3, col4 = st.columns(4)

if "error" not in kpis:
    col1.metric("Отслеживаемых каналов", kpis.get("total_channels", 0))
    col2.metric("Суммарно просмотров", f"{kpis.get('total_views', 0):,}")
    col3.metric("Общее число подписчиков", f"{kpis.get('total_subscribers', 0):,}")
    col4.metric("Средний ER (вовлеченность)", f"{kpis.get('engagement_rate_pct', 0.0)}%")
else:
    st.warning("⚠️ Не удалось подключиться к FastAPI бэкенду. Убедитесь, что бэкенд запущен.")

st.markdown("---")

# Section: Top Videos by Views
st.subheader("🔥 Топ роликов по просмотрам")

# Channel filter & Limit selection
channels = client.get_channels()
channel_options = {"Все каналы": None}
if channels and not isinstance(channels, dict):
    for c in channels:
        label = c.get("title") or c.get("custom_url") or c.get("channel_id")
        if c.get("custom_url"):
            label = f"{c.get('title')} ({c.get('custom_url')})"
        channel_options[label] = c.get("channel_id")

col_filter, col_limit = st.columns([3, 1])
with col_filter:
    selected_channel_label = st.selectbox(
        "Фильтр по каналу:",
        options=list(channel_options.keys()),
        index=0,
        help="Выберите конкретный канал или просматривайте общий рейтинг по всем конкурентам"
    )
with col_limit:
    selected_limit = st.selectbox(
        "Количество роликов:",
        options=[10, 20, 30, 50],
        index=1,
        help="Максимальное число видео в выборке"
    )

selected_channel_id = channel_options.get(selected_channel_label)
videos = client.get_videos(channel_id=selected_channel_id, limit=selected_limit)

if videos:
    df_videos = pd.DataFrame(videos)
    # Generate direct YouTube link
    df_videos["youtube_url"] = "https://www.youtube.com/watch?v=" + df_videos["video_id"].astype(str)
    if "channel_title" not in df_videos.columns or df_videos["channel_title"].isnull().all():
        df_videos["channel_title"] = selected_channel_label if selected_channel_id else "YouTube Канал"
    df_videos["channel_title"] = df_videos["channel_title"].fillna("YouTube Канал")

    df_videos["short_title"] = df_videos["title"].apply(lambda t: t[:45] + "..." if len(str(t)) > 45 else str(t))

    chart_col, preview_col = st.columns([3, 2])

    with chart_col:
        chart_n = min(10, len(df_videos))
        chart_title = f"Топ-{chart_n} видео ({selected_channel_label})" if selected_channel_id else f"Топ-{chart_n} видео (с разбивкой по каналам)"
        # Plotly horizontal bar chart colored by channel
        fig = px.bar(
            df_videos.head(chart_n),
            x="view_count",
            y="short_title",
            orientation="h",
            color="channel_title",
            labels={
                "view_count": "Количество просмотров",
                "short_title": "Видео",
                "channel_title": "Канал"
            },
            hover_name="title",
            hover_data={
                "view_count": ":,",
                "like_count": ":,",
                "channel_title": True,
                "short_title": False
            },
            title=chart_title
        )
        fig.update_layout(
            yaxis={"autorange": "reversed"},
            height=430,
            margin=dict(l=10, r=10, t=40, b=10),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig, use_container_width=True)

    with preview_col:
        st.markdown("##### 🏆 Лидеры просмотров")
        top_3 = df_videos.head(3)
        for _, v in top_3.iterrows():
            with st.container(border=True):
                card_img, card_info = st.columns([1, 2])
                with card_img:
                    thumb = v.get("thumbnail_url")
                    if thumb:
                        st.image(thumb, use_container_width=True)
                with card_info:
                    st.markdown(f"**[{v['title']}]({v['youtube_url']})**")
                    st.caption(f"📺 Канал: **{v.get('channel_title', 'Не указан')}**")
                    st.markdown(f"👁️ **{v['view_count']:,}** просмотров • 👍 **{v.get('like_count', 0):,}**")
                    st.link_button("▶️ Открыть на YouTube", v["youtube_url"], use_container_width=True)

    # Detailed Table with Direct Links and Thumbnails
    st.markdown("#### 📋 Детальная таблица роликов")
    display_cols = ["thumbnail_url", "title", "channel_title", "view_count", "like_count", "published_at", "youtube_url"]
    existing_cols = [c for c in display_cols if c in df_videos.columns]

    st.dataframe(
        df_videos[existing_cols],
        column_config={
            "thumbnail_url": st.column_config.ImageColumn("Обложка", width="small"),
            "title": st.column_config.TextColumn("Название видео", width="large"),
            "channel_title": st.column_config.TextColumn("Канал", width="medium"),
            "view_count": st.column_config.NumberColumn("Просмотры", format="%d"),
            "like_count": st.column_config.NumberColumn("Лайки", format="%d"),
            "published_at": st.column_config.DatetimeColumn("Дата публикации", format="DD.MM.YYYY HH:mm"),
            "youtube_url": st.column_config.LinkColumn("YouTube", display_text="▶️ Смотреть"),
        },
        hide_index=True,
        use_container_width=True
    )
else:
    if selected_channel_id:
        st.info(f"Нет данных о видео для канала **{selected_channel_label}**.")
    else:
        st.info("Нет данных о видео. Перейдите во вкладку '⚙️ Управление каналами' для синхронизации.")

st.markdown("---")

# Architectural overview in an expander
with st.expander("📌 Архитектурный статус платформы (Google Cloud)", expanded=False):
    st.markdown("""
    - **Очереди задач**: Google Cloud Tasks (`telegram-tasks`)
    - **Горячий кэш**: Firestore Native Mode (TTL 24h, <50ms)
    - **DWH & Аналитика**: BigQuery Views (`v_latest_channel_stats`)
    - **Изолированная песочница**: `code-sandbox` (512MB RAM)
    - **AI Core**: Vertex AI Gemini 3.5 Flash
    
    👉 **Разделы в боковом меню:**
    - **🏠 Главная**: Сводные KPI, топ видеороликов и прямые ссылки на YouTube
    - **📈 Динамика**: Анализ трендов и лидерборды конкурентов
    - **💬 AI-Аналитик**: Интеллектуальный диалог с Gemini 3.5 Flash
    - **⚙️ Управление каналами**: Добавление и удаление каналов, пользователи Telegram
    """)
