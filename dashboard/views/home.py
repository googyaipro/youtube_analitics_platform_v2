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

# Enforce authentication
user = require_auth()
client = get_api_client()


def fmt_num(val) -> str:
    """Safely format numbers with thousands separators without crashing on strings, Decimal, or None."""
    try:
        if val is None or val == "" or str(val).strip().lower() == "nan":
            return "0"
        return f"{int(float(val)):,}"
    except (ValueError, TypeError):
        return str(val)

# --- Sidebar: Channel Set Selector ---
with st.sidebar:
    st.markdown(f"### 📁 {t('active_set')}")
    channel_sets = client.get_channel_sets()

    if not channel_sets:
        st.warning(t("no_channels"))
        # Auto-create first set if empty
        try:
            created = client.create_channel_set({
                "name": "Primary",
                "description": "Primary competitor monitoring set"
            })
            channel_sets = [created]
        except Exception:
            channel_sets = []

    set_options = {s["name"]: s["id"] for s in channel_sets}
    active_set_id = user.get("active_set_id")
    
    current_idx = 0
    if active_set_id:
        for idx, (name, s_id) in enumerate(set_options.items()):
            if s_id == active_set_id:
                current_idx = idx
                break

    if set_options:
        selected_set_name = st.selectbox(
            t("select_set"),
            options=list(set_options.keys()),
            index=current_idx,
            key="active_set_select"
        )
        selected_set_id = set_options.get(selected_set_name)
        if selected_set_id and selected_set_id != active_set_id:
            try:
                client.activate_channel_set(selected_set_id)
                user["active_set_id"] = selected_set_id
                st.session_state["user"] = user
                st.rerun()
            except Exception as e:
                st.error(f"Failed to switch set: {e}")
    else:
        selected_set_id = None

    # Check API keys warning
    if not user.get("youtube_api_key_valid"):
        st.warning(f"⚠️ {t('key_invalid')}. Configure YouTube Data API key in profile.")
    if not user.get("gemini_api_key_valid"):
        st.info("💡 Gemini API Key is not set. Add it in profile for AI analysis.")

    st.markdown("---")


# --- Main Dashboard Header ---
col_head, col_btn = st.columns([2, 2])
with col_head:
    st.title(f"🎬 {t('app_title')}")
    st.caption(f"{t('app_tagline')} | {t('active_set')}: **{selected_set_name if set_options else 'None'}**")

with col_btn:
    st.write("")
    col_r1, col_r2, col_r3 = st.columns([1, 1, 1])
    with col_r1:
        if st.button(f"🔄 {t('sync_now')}", use_container_width=True):
            if selected_set_id:
                with st.spinner(t("syncing")):
                    try:
                        res = client.sync_channel_set(selected_set_id)
                        synced_count = res.get('snapshots_synced', res.get('snapshots_saved', 0))
                        st.success(f"{t('sync_success')} ({synced_count})")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Sync error: {e}")
    with col_r2:
        if st.button("📢 AI-Дайджест", use_container_width=True):
            if selected_set_id:
                with st.spinner("Генерирую executive AI-дайджест ниши..."):
                    try:
                        d_res = client.get_channel_set_digest(selected_set_id)
                        st.session_state["active_digest"] = d_res.get("digest")
                    except Exception as e:
                        st.error(f"Digest error: {e}")
    with col_r3:
        if st.button("Refresh", use_container_width=True):
            st.rerun()

if "active_digest" in st.session_state and st.session_state["active_digest"]:
    with st.expander("📢 **Executive AI-Дайджест ниши**", expanded=True):
        st.markdown(st.session_state["active_digest"])
        if st.button("✕ Скрыть дайджест", key="close_digest"):
            del st.session_state["active_digest"]
            st.rerun()

# --- Section 1: KPI Cards ---
kpis = client.get_kpis(set_id=selected_set_id)

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric(t("kpi_channels"), kpis.get("total_channels", 0))
col2.metric(t("kpi_videos"), kpis.get("total_videos", 0))
col3.metric(t("kpi_views"), fmt_num(kpis.get("total_views", 0)))
col4.metric(t("kpi_avg_views"), fmt_num(kpis.get("avg_views_per_video", 0)))
col5.metric(t("kpi_viral_hits"), kpis.get("viral_hits_count", 0))

st.markdown("---")

# --- Section 2: Top Videos & Virality Breakdown ---
st.subheader(f"🔥 {t('top_videos')}")

# Filter by channel inside this set
channels = client.get_channels(set_id=selected_set_id)
channel_options = {"All Channels": None}
for c in channels:
    label = c.get("title") or c.get("custom_url") or c.get("channel_id")
    channel_options[label] = c.get("channel_id")

col_filter, col_limit = st.columns([3, 1])
with col_filter:
    selected_ch_label = st.selectbox("Channel Filter:", options=list(channel_options.keys()))
with col_limit:
    selected_limit = st.selectbox("Limit:", options=[10, 20, 50, 100], index=1)

selected_channel_id = channel_options.get(selected_ch_label)
videos = client.get_videos(set_id=selected_set_id, channel_id=selected_channel_id, limit=selected_limit)

if not videos:
    st.info(t("no_channels"))
else:
    df = pd.DataFrame(videos)
    df["youtube_link"] = "https://www.youtube.com/watch?v=" + df["video_id"].astype(str)
    df["badges_str"] = df["badges"].apply(lambda b: " ".join(b) if isinstance(b, list) else "")

    # Top Video Chart (Horizontal Bar)
    top_chart_data = df.head(10).copy()
    top_chart_data["short_title"] = top_chart_data["title"].apply(lambda x: x[:35] + "..." if len(str(x)) > 35 else str(x))
    
    fig = px.bar(
        top_chart_data,
        x="view_count",
        y="short_title",
        orientation="h",
        color="outlier_score",
        color_continuous_scale="Blues",
        labels={"view_count": t("views"), "short_title": t("video_title"), "outlier_score": t("outlier_score")},
        title=t("top_videos")
    )
    fig.update_layout(yaxis={"autorange": "reversed"}, height=350, margin={"l": 0, "r": 20, "t": 40, "b": 20})
    st.plotly_chart(fig, use_container_width=True)

    # Videos List & Factor Analysis Expanders
    st.markdown(f"#### 📋 {t('top_videos')} ({len(df)})")
    
    for idx, v in df.iterrows():
        badges_display = f" `{v['badges_str']}`" if v["badges_str"] else ""
        expander_title = f"#{idx+1} | {fmt_num(v.get('view_count', 0))} views | {v.get('outlier_score', 1.0)}x | {v.get('channel_title', '')} — «{v.get('title', '')}»{badges_display}"
        
        with st.expander(expander_title):
            c_thumb, c_stats, c_ai = st.columns([2, 3, 4])
            
            with c_thumb:
                if v.get("thumbnail_url"):
                    st.image(v["thumbnail_url"], use_container_width=True)
                st.markdown(f"[▶️ YouTube]({v['youtube_link']})")

            with c_stats:
                st.markdown(f"**Channel:** {v.get('channel_title', '')}")
                st.markdown(f"**Views:** {fmt_num(v.get('view_count', 0))}")
                st.markdown(f"**Channel Avg:** {fmt_num(v.get('channel_avg_views', 0))}")
                st.markdown(f"**Multiplier (Outlier):** `{v.get('outlier_score', 1.0)}x`")
                st.markdown(f"**Velocity (VPH):** `{v.get('velocity_vph', 0.0)}`")
                st.markdown(f"**Engagement (ER):** `{v.get('engagement_rate_pct', 0.0)}%`")
                st.markdown(f"**Published:** {str(v.get('published_at'))[:10]}")

            with c_ai:
                st.markdown(f"##### {t('explain_ai_btn')}")
                explain_key = f"explain_{v['video_id']}"
                
                if st.button(f"🔍 Gemini Analysis", key=f"btn_{explain_key}"):
                    with st.spinner("Analyzing with Gemini 3.8 Flash..."):
                        try:
                            res = client.explain_video(v["video_id"], set_id=selected_set_id)
                            st.session_state[explain_key] = res.get("explanation", {})
                        except Exception as e:
                            st.error(f"Error: {e}")

                if explain_key in st.session_state:
                    exp = st.session_state[explain_key]
                    st.success(f"🎯 **{t('ai_verdict')}:** {exp.get('verdict', '')}")
                    st.info(f"🎣 **{t('ai_hook')}:** {exp.get('hook_analysis', '')}")
                    st.markdown(f"🔥 **{t('ai_trend')}:** {exp.get('trend_alignment', '')}")
                    st.markdown(f"💡 **{t('ai_actionable')}:** {exp.get('actionable_takeaway', '')}")
