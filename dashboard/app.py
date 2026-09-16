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
st.caption("Powered by Google Cloud (BigQuery & Cloud Storage) + FastAPI + Streamlit")

# Fetch KPIs
kpis = client.get_kpis()

col1, col2, col3, col4 = st.columns(4)

if "error" not in kpis:
    col1.metric("Tracked Channels", kpis.get("total_channels", 0))
    col2.metric("Total Views Analyzed", f"{kpis.get('total_views', 0):,}")
    col3.metric("Total Subscribers", f"{kpis.get('total_subscribers', 0):,}")
    col4.metric("Avg Engagement Rate", f"{kpis.get('engagement_rate_pct', 0.0)}%")
else:
    st.warning("⚠️ Could not connect to FastAPI backend. Ensure backend is running (`uvicorn backend.main:app`).")

st.markdown("---")

# Quick Overview Layout
left_col, right_col = st.columns([2, 1])

with left_col:
    st.subheader("🔥 Top Performing Videos")
    videos = client.get_videos(limit=10)
    if videos:
        df_videos = pd.DataFrame(videos)
        fig = px.bar(
            df_videos,
            x="view_count",
            y="title",
            orientation="h",
            labels={"view_count": "Views", "title": "Video Title"},
            title="Most Viewed Videos",
            color="view_count",
            color_continuous_scale="Viridis"
        )
        fig.update_layout(yaxis={"autorange": "reversed"}, height=420)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No video records found. Use the Ingestion page to sync your first channel.")

with right_col:
    st.subheader("📌 Platform Status")
    st.markdown("""
    - **Backend API**: `Active`
    - **Data Warehouse**: Google Cloud BigQuery
    - **Data Lake Archive**: Google Cloud Storage
    - **Source API**: YouTube Data API v3
    
    👉 Navigate using the sidebar:
    - **📊 Channel Overview**: Deep dive into channel statistics
    - **🎬 Video Performance**: Engagement & video charts
    - **🔄 Data Ingestion**: Trigger ETL jobs for any channel
    """)

st.markdown("---")
st.subheader("📋 Recent Ingested Records")
if videos:
    display_df = pd.DataFrame(videos)[["title", "channel_title", "view_count", "like_count", "comment_count", "published_at"]]
    display_df.columns = ["Title", "Channel", "Views", "Likes", "Comments", "Published At"]
    st.dataframe(display_df, use_container_width=True)
