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
st.title("🎬 YouTube Analytics Platform")
st.caption("Serverless платформа на базе Google Cloud (Cloud Run, Cloud Tasks, BigQuery, Firestore, Vertex AI)")

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

left_col, right_col = st.columns([2, 1])

with left_col:
    st.subheader("🔥 Топ роликов по просмотрам")
    videos = client.get_videos(limit=10)
    if videos:
        df_videos = pd.DataFrame(videos)
        fig = px.bar(
            df_videos,
            x="view_count",
            y="title",
            orientation="h",
            labels={"view_count": "Просмотры", "title": "Название видео"},
            color="view_count",
            color_continuous_scale="Reds"
        )
        fig.update_layout(yaxis={"autorange": "reversed"}, height=400)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Нет данных о видео. Перейдите во вкладку 'Управление списком' для синхронизации.")

with right_col:
    st.subheader("📌 Архитектурный статус")
    st.markdown("""
    - **Очереди задач**: Google Cloud Tasks (`telegram-tasks`)
    - **Горячий кэш**: Firestore Native Mode (TTL 24h, <50ms)
    - **DWH & Аналитика**: BigQuery Views (`v_latest_channel_stats`)
    - **Изолированная песочница**: `code-sandbox` (512MB RAM)
    - **AI Core**: Vertex AI Gemini 3.5 Flash
    
    👉 **Навигация в боковом меню:**
    - **📈 1_Time_Series**: Анализ трендов и динамики каналов
    - **💬 2_AI_Analyst**: Интерактивный чат с AI-аналитиком
    - **⚙️ 3_Competitors_Mgmt**: Управление списком конкурентов
    """)
