import logging
from pathlib import Path
from typing import Optional
import streamlit as st

try:
    from dashboard.utils.i18n import t, get_current_language
except ModuleNotFoundError:
    from utils.i18n import t, get_current_language

logger = logging.getLogger(__name__)

HELP_LOCALES_DIR = Path(__file__).resolve().parent.parent / "locales" / "help"
_HELP_CACHE = {}


def get_help_markdown(lang: Optional[str] = None) -> str:
    """Load localized help and methodology markdown content."""
    if not lang:
        lang = get_current_language()

    if lang in _HELP_CACHE:
        return _HELP_CACHE[lang]

    filepath = HELP_LOCALES_DIR / f"{lang}.md"
    if not filepath.exists():
        filepath = HELP_LOCALES_DIR / "en.md"
    if not filepath.exists():
        filepath = HELP_LOCALES_DIR / "ru.md"

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
            _HELP_CACHE[lang] = content
            return content
    except Exception as e:
        logger.error(f"Error reading help markdown for {lang}: {e}")
        return "# 📖 Help & Methodology\n\nHelp content is temporarily unavailable."


if hasattr(st, "dialog"):
    @st.dialog(t("help_modal_title"), width="large")
    def _render_help_dialog(content: str):
        """Render fullscreen wide dialog for in-depth methodology review."""
        st.markdown(content)
        if st.button(f"✖ {t('btn_close')}", use_container_width=True, key="btn_close_help_dialog"):
            st.session_state["show_help_modal"] = False
            st.rerun()
else:
    def _render_help_dialog(content: str):
        st.markdown(content)


def render_help_drawer():
    """
    Renders an interactive, collapsible side panel in the sidebar.
    Can be opened and closed at any time by the user, and strictly follows user language.
    """
    lang = get_current_language()
    content = get_help_markdown(lang)

    with st.sidebar:
        # Check if modal was triggered
        if st.session_state.get("show_help_modal"):
            _render_help_dialog(content)

        is_open = st.session_state.get("show_help_drawer", False)

        # Primary toggle button in sidebar
        btn_icon = "📖" if not is_open else "✖"
        btn_label = f"{btn_icon} {t('help_sidebar_title')}"
        if st.button(btn_label, use_container_width=True, key="btn_help_drawer_toggle"):
            st.session_state["show_help_drawer"] = not is_open
            st.rerun()

        # Side panel content container
        if is_open:
            with st.container(border=True):
                col_close, col_expand = st.columns([1, 1])
                with col_close:
                    if st.button(f"✖ {t('btn_close')}", key="btn_help_inner_close", use_container_width=True):
                        st.session_state["show_help_drawer"] = False
                        st.rerun()
                with col_expand:
                    if hasattr(st, "dialog"):
                        if st.button(f"🔍 {t('help_modal_btn')}", key="btn_help_inner_modal", use_container_width=True):
                            st.session_state["show_help_modal"] = True
                            st.rerun()

                st.markdown("---")
                st.markdown(content)
                st.markdown("---")

                if st.button(f"▲ {t('btn_close')}", key="btn_help_bottom_close", use_container_width=True):
                    st.session_state["show_help_drawer"] = False
                    st.rerun()
