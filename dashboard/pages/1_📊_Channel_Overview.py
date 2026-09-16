import streamlit as st
import pandas as pd
import plotly.express as px
from utils.api_client import APIClient

st.set_page_config(page_title="Channel Overview", page_icon="📊", layout="wide")
st.title("📊 Channel Overview & Comparative Analytics")

client = APIClient()
channels = client.get_channels()

if not channels:
    st.info("No channels found. Ingest a channel using the **Data Ingestion** tab.")
else:
    df_channels = pd.DataFrame(channels)
    
    st.subheader("Channels Summary")
    st.dataframe(
        df_channels[["title", "custom_url", "subscriber_count", "view_count", "video_count", "country"]],
        use_container_width=True
    )
    
    col1, col2 = st.columns(2)
    with col1:
        fig_sub = px.bar(
            df_channels,
            x="title",
            y="subscriber_count",
            title="Subscribers per Channel",
            color="title",
            text_auto=True
        )
        st.plotly_chart(fig_sub, use_container_width=True)

    with col2:
        fig_views = px.bar(
            df_channels,
            x="title",
            y="view_count",
            title="Total Channel Views",
            color="title",
            text_auto=True
        )
        st.plotly_chart(fig_views, use_container_width=True)
