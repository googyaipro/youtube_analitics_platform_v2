import streamlit as st
import pandas as pd
import plotly.express as px
from utils.api_client import APIClient

st.set_page_config(page_title="Video Performance", page_icon="🎬", layout="wide")
st.title("🎬 Video Performance & Engagement Analytics")

client = APIClient()
channels = client.get_channels()

# Channel filter
channel_options = {"All Channels": None}
for c in channels:
    channel_options[c.get("title", c.get("channel_id"))] = c.get("channel_id")

selected_channel_label = st.selectbox("Filter by Channel:", list(channel_options.keys()))
selected_channel_id = channel_options[selected_channel_label]

videos = client.get_videos(channel_id=selected_channel_id, limit=100)

if not videos:
    st.warning("No videos available for the selected channel.")
else:
    df = pd.DataFrame(videos)
    # Calculate Engagement Rate %
    df["engagement_rate_%"] = ((df["like_count"] + df["comment_count"]) / df["view_count"] * 100).round(2)

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Correlation: Views vs Likes")
        fig_scatter = px.scatter(
            df,
            x="view_count",
            y="like_count",
            size="comment_count",
            hover_data=["title"],
            color="engagement_rate_%",
            title="Views vs Likes (Bubble Size = Comments)",
            labels={"view_count": "Total Views", "like_count": "Total Likes"}
        )
        st.plotly_chart(fig_scatter, use_container_width=True)

    with col2:
        st.subheader("Engagement Rate Distribution")
        fig_eng = px.histogram(
            df,
            x="engagement_rate_%",
            nbins=15,
            title="Distribution of Engagement Rates (%)",
            color_discrete_sequence=["#636EFA"]
        )
        st.plotly_chart(fig_eng, use_container_width=True)

    st.markdown("---")
    st.subheader("Detailed Video Records")
    st.dataframe(
        df[["title", "channel_title", "view_count", "like_count", "comment_count", "engagement_rate_%", "published_at"]],
        use_container_width=True
    )
