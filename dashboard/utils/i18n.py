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
    """Update current language in session state and synchronize all selector keys."""
    if lang in SUPPORTED_LANGUAGES:
        st.session_state["language"] = lang
        st.session_state["global_lang_selector"] = lang
        st.session_state["profile_lang_selector"] = lang
        if "user" in st.session_state and isinstance(st.session_state["user"], dict):
            st.session_state["user"]["language"] = lang


def update_active_language(new_lang: str):
    """Atomically update language across all session state keys, user profile, and backend."""
    if new_lang not in SUPPORTED_LANGUAGES:
        return
    set_language(new_lang)

    # Persist to backend if authenticated
    if st.session_state.get("access_token"):
        try:
            try:
                from dashboard.utils.api_client import get_api_client
            except ModuleNotFoundError:
                from utils.api_client import get_api_client
            client = get_api_client()
            client.update_user_language(new_lang)
        except Exception as e:
            logger.debug(f"Could not persist language to backend: {e}")


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


def _on_lang_dropdown_change(selector_key: str):
    val = st.session_state.get(selector_key)
    if val and val in SUPPORTED_LANGUAGES:
        update_active_language(val)


def render_language_selector(sidebar: bool = True, key: str = "global_lang_selector"):
    """Render a compact dropdown language switcher with bulletproof state synchronization."""
    current_lang = get_current_language()
    options = list(SUPPORTED_LANGUAGES.keys())

    # Pre-sync widget session state key so Streamlit never sees a stale value
    if key in st.session_state and st.session_state[key] != current_lang:
        st.session_state[key] = current_lang

    try:
        current_idx = options.index(current_lang)
    except ValueError:
        current_idx = 0

    target = st.sidebar if sidebar else st
    target.selectbox(
        "🌐 Language",
        options=options,
        index=current_idx,
        format_func=lambda code: SUPPORTED_LANGUAGES.get(code, code),
        key=key,
        on_change=_on_lang_dropdown_change,
        args=(key,)
    )
