import os
import sys

# Ensure project root is in sys.path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

import streamlit as st
import pandas as pd
import plotly.express as px
try:
    from dashboard.utils.api_client import get_api_client
    from dashboard.utils.auth_ui import require_auth
    from dashboard.utils.i18n import t
except ModuleNotFoundError:
    from utils.api_client import get_api_client
    from utils.auth_ui import require_auth
    from utils.i18n import t

user = require_auth()
client = get_api_client()

active_set_id = user.get("active_set_id")

st.title(f"📈 {t('nav_dynamics')}")
st.caption(t("app_tagline"))

channels = client.get_channels(set_id=active_set_id)
videos = client.get_videos(set_id=active_set_id, limit=100)

if not channels:
    st.info(t("no_channels"))
else:
    df_channels = pd.DataFrame(channels)

    # 1. Channels leaderboard
    st.subheader(f"🏆 {t('kpi_channels')}")
    col1, col2 = st.columns(2)

    with col1:
        fig_subs = px.bar(
            df_channels.sort_values(by="subscriber_count", ascending=False),
            x="title",
            y="subscriber_count",
            color="subscriber_count",
            title=t("chart_subs_title"),
            labels={"title": t("channel_title"), "subscriber_count": t("chart_subs_label")},
            color_continuous_scale="Blues"
        )
        st.plotly_chart(fig_subs, use_container_width=True)

    with col2:
        fig_views = px.bar(
            df_channels.sort_values(by="view_count", ascending=False),
            x="title",
            y="view_count",
            color="view_count",
            title=t("chart_views_title"),
            labels={"title": t("channel_title"), "view_count": t("views")},
            color_continuous_scale="Teal"
        )
        st.plotly_chart(fig_views, use_container_width=True)

    # 2. Virality Matrix (Scatter plot)
    if videos:
        st.markdown("---")
        st.subheader(f"🎯 {t('virality_matrix_title')}")
        df_v = pd.DataFrame(videos)
        df_v["bubble_size"] = pd.to_numeric(df_v.get("velocity_vph", 1.0), errors="coerce").fillna(1.0).clip(lower=1.0)
        
        fig_scatter = px.scatter(
            df_v,
            x="view_count",
            y="outlier_score",
            size="bubble_size",
            color="channel_title",
            hover_name="title",
            hover_data={"bubble_size": False, "velocity_vph": True},
            labels={
                "view_count": t("views"),
                "outlier_score": t("outlier_score"),
                "velocity_vph": t("velocity"),
                "channel_title": t("channel_title")
            },
            title=t("virality_matrix_chart_title")
        )
        fig_scatter.add_hline(y=1.8, line_dash="dash", line_color="red", annotation_text=t("viral_threshold_annotation"))
        st.plotly_chart(fig_scatter, use_container_width=True)

    # 3. Channels Table
    st.markdown("---")
    st.subheader(f"📋 {t('kpi_channels')}")
    df_channels["channel_url"] = df_channels.apply(
        lambda r: f"https://www.youtube.com/{r['custom_url']}" if r.get("custom_url") and str(r["custom_url"]).startswith("@") else f"https://www.youtube.com/channel/{r['channel_id']}",
        axis=1
    )
    column_mapping = {
        "title": t("channel_title"),
        "custom_url": "Handle",
        "subscriber_count": "Subscribers",
        "view_count": t("views"),
        "video_count": "Total Videos",
        "channel_url": "YouTube"
    }
    cols_to_show = [c for c in column_mapping.keys() if c in df_channels.columns]
    df_display = df_channels[cols_to_show].rename(columns=column_mapping)
    st.dataframe(
        df_display,
        column_config={
            "YouTube": st.column_config.LinkColumn("YouTube", display_text="🔗 Channel Link"),
            "Subscribers": st.column_config.NumberColumn("Subscribers", format="%d"),
            t("views"): st.column_config.NumberColumn(t("views"), format="%d"),
            "Total Videos": st.column_config.NumberColumn("Total Videos", format="%d"),
        },
        hide_index=True,
        use_container_width=True
    )
