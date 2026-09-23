import json
import logging
from pathlib import Path
from typing import Dict, Optional
import streamlit as st

logger = logging.getLogger(__name__)

SUPPORTED_LANGUAGES = {
    "en": "🇺🇸 English",
    "ru": "🇷🇺 Русский",
    "de": "🇩🇪 Deutsch",
    "fi": "🇫🇮 Suomi",
    "ka": "🇬🇪 ქართული"
}

LOCALES_DIR = Path(__file__).resolve().parent.parent / "locales"
_TRANSLATIONS_CACHE: Dict[str, Dict[str, str]] = {}


def load_translations(lang: str) -> Dict[str, str]:
    """Load JSON translation dictionary for a specific language."""
    if lang in _TRANSLATIONS_CACHE:
        return _TRANSLATIONS_CACHE[lang]

    filepath = LOCALES_DIR / f"{lang}.json"
    if not filepath.exists():
        filepath = LOCALES_DIR / "en.json"

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            _TRANSLATIONS_CACHE[lang] = data
            return data
    except Exception as e:
        logger.error(f"Error loading translation for {lang}: {e}")
        return {}


def get_current_language() -> str:
    """Retrieve current UI language from session state."""
    if "language" not in st.session_state:
        st.session_state["language"] = "en"
    return st.session_state["language"]


def set_language(lang: str):
    """Update current language in session state."""
    if lang in SUPPORTED_LANGUAGES:
        st.session_state["language"] = lang


def t(key: str, default: Optional[str] = None) -> str:
    """Translate key based on currently selected language."""
    lang = get_current_language()
    trans = load_translations(lang)
    val = trans.get(key)
    if val is not None:
        return val

    # Fallback to English, then Russian
    if lang != "en":
        en_trans = load_translations("en")
        if key in en_trans:
            return en_trans[key]
    ru_trans = load_translations("ru")
    return ru_trans.get(key, default or key)


def render_language_selector(sidebar: bool = True):
    """Render a compact dropdown language switcher."""
    current_lang = get_current_language()
    options = list(SUPPORTED_LANGUAGES.keys())
    try:
        current_idx = options.index(current_lang)
    except ValueError:
        current_idx = 0

    target = st.sidebar if sidebar else st
    selected_lang = target.selectbox(
        "🌐 Language / Язык",
        options=options,
        index=current_idx,
        format_func=lambda code: SUPPORTED_LANGUAGES.get(code, code),
        key="global_lang_selector"
    )

    if selected_lang != current_lang:
        set_language(selected_lang)
        # Attempt to sync with backend if user is logged in
        if st.session_state.get("access_token"):
            try:
                try:
                    from dashboard.utils.api_client import get_api_client
                except ModuleNotFoundError:
                    from utils.api_client import get_api_client
                client = get_api_client()
                client.update_user_language(selected_lang)
            except Exception:
                pass
        st.rerun()
