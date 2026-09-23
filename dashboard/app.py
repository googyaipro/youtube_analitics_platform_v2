import os
import sys

# Ensure project root is in sys.path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

import streamlit as st

try:
    from dashboard.utils.i18n import t
except ModuleNotFoundError:
    from utils.i18n import t

# Global layout configuration
st.set_page_config(
    page_title="YouTube Analytics Platform",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Navigation definition with dynamic localized titles and clean URL paths
pages = [
    st.Page(
        "views/home.py",
        title=t("nav_home"),
        icon="🏠",
        default=True,
    ),
    st.Page(
        "views/dynamics.py",
        title=t("nav_dynamics"),
        icon="📈",
        url_path="dynamics",
    ),
    st.Page(
        "views/ai_analyst.py",
        title=t("nav_ai_analyst"),
        icon="💬",
        url_path="ai-analyst",
    ),
    st.Page(
        "views/channel_sets.py",
        title=t("nav_channel_sets"),
        icon="⚙️",
        url_path="channel-sets",
    ),
    st.Page(
        "views/profile.py",
        title=t("nav_profile"),
        icon="🔑",
        url_path="profile",
    ),
]

pg = st.navigation(pages)
pg.run()
