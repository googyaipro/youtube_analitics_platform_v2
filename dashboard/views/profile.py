import os
import sys

# Ensure project root is in sys.path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

import streamlit as st
try:
    from dashboard.utils.api_client import get_api_client
    from dashboard.utils.auth_ui import require_auth
    from dashboard.utils.i18n import t, SUPPORTED_LANGUAGES, set_language, get_current_language
except ModuleNotFoundError:
    from utils.api_client import get_api_client
    from utils.auth_ui import require_auth
    from utils.i18n import t, SUPPORTED_LANGUAGES, set_language, get_current_language

user = require_auth()
client = get_api_client()

st.title(f"🔑 {t('profile_title')}")
st.caption(f"{t('profile_subtitle')}")

col_keys, col_tg = st.columns([3, 2])

# --- Column 1: API Keys (BYOK) ---
with col_keys:
    st.subheader("🛠️ Personal API Keys (BYOK)")
    st.info(
        "💡 **Why your own keys?**\n"
        "1. **Free:** YouTube Data API provides 10,000 units/day for free. Google AI Studio provides Gemini 3.8 Flash for free (15 requests/minute).\n"
        "2. **Secure:** Your keys are encrypted with AES-256 (Fernet) and accessible only within your authenticated account."
    )

    # 1. YouTube Data API Key
    st.markdown(f"#### 1. {t('yt_key_label')}")
    yt_input = st.text_input(
        t("yt_key_label"),
        type="password",
        placeholder="AIzaSy...",
        help="Obtain key in Google Cloud Console (YouTube Data API v3)"
    )

    c_test_yt, c_status_yt = st.columns([1, 2])
    with c_test_yt:
        if st.button(t("test_yt_btn"), key="btn_test_yt"):
            if not yt_input.strip():
                st.warning("Enter key to test.")
            else:
                with st.spinner("Testing YouTube API key..."):
                    try:
                        res = client.verify_key("youtube", yt_input.strip())
                        if res.get("is_valid") or res.get("valid"):
                            user["youtube_api_key_valid"] = True
                            st.session_state["user"] = user
                            st.success(f"✅ {res.get('message')}")
                        else:
                            st.error(f"❌ {res.get('message')}")
                    except Exception as e:
                        st.error(f"Error verifying key: {e}")

    with c_status_yt:
        if user.get("youtube_api_key_valid"):
            st.success(f"🟢 {t('key_valid')}")
        else:
            st.warning("🔴 Key not configured")

    st.markdown("---")

    # 2. Gemini API Key
    st.markdown(f"#### 2. {t('gemini_key_label')}")
    gemini_input = st.text_input(
        t("gemini_key_label"),
        type="password",
        placeholder="AIzaSy...",
        help="Free key from aistudio.google.com"
    )

    c_test_gem, c_status_gem = st.columns([1, 2])
    with c_test_gem:
        if st.button(t("test_gemini_btn"), key="btn_test_gemini"):
            if not gemini_input.strip():
                st.warning("Enter key to test.")
            else:
                with st.spinner("Testing Gemini API key..."):
                    try:
                        res = client.verify_key("gemini", gemini_input.strip())
                        if res.get("is_valid") or res.get("valid"):
                            user["gemini_api_key_valid"] = True
                            st.session_state["user"] = user
                            st.success(f"✅ {res.get('message')}")
                        else:
                            st.error(f"❌ {res.get('message')}")
                    except Exception as e:
                        st.error(f"Error verifying key: {e}")

    with c_status_gem:
        if user.get("gemini_api_key_valid"):
            st.success(f"🟢 {t('key_valid')}")
        else:
            st.warning("🔴 Key not configured")

    st.markdown("---")

    # Save button
    if st.button(f"💾 {t('save_keys_btn')}", type="primary", use_container_width=True):
        if not yt_input.strip() and not gemini_input.strip():
            st.warning("Enter at least one key to save.")
        else:
            try:
                res = client.update_user_keys(
                    youtube_key=yt_input.strip() if yt_input.strip() else None,
                    gemini_key=gemini_input.strip() if gemini_input.strip() else None
                )
                st.success("API keys encrypted and saved successfully!")
                user["youtube_api_key_valid"] = res.get("youtube_key_valid")
                user["gemini_api_key_valid"] = res.get("gemini_key_valid")
                st.session_state["user"] = user
                st.rerun()
            except Exception as e:
                st.error(f"Error saving keys: {e}")


# --- Column 2: Telegram & Language Settings ---
with col_tg:
    st.subheader(f"🤖 {t('telegram_integration')}")
    st.caption(t("telegram_desc"))

    tg_chat_id = user.get("telegram_chat_id")
    if tg_chat_id:
        st.success(f"✅ {t('telegram_linked')} (Chat ID: `{tg_chat_id}`)")
        st.markdown(
            "You will receive scheduled digests for your channel sets directly in Telegram. "
            "You can also use bot commands: `/sets`, `/top`, `/explain 1`, `/status`."
        )
    else:
        st.warning(f"⚠️ {t('telegram_not_linked')}")
        st.markdown("Click the button below to generate a secure one-time link:")
        
        if st.button(f"🔗 {t('link_telegram_btn')}", use_container_width=True):
            try:
                link_data = client.generate_telegram_link()
                link_url = link_data.get("link_url")
                if link_url:
                    st.markdown(f"### [👉 Open Telegram Bot]({link_url})")
                    st.info(f"Or send command manually:\n`/start {link_data.get('link_code')}`")
            except Exception as e:
                st.error(f"Error generating link: {e}")

    st.markdown("---")
    st.subheader(f"🌐 {t('language_label')}")
    current_lang = user.get("language") or get_current_language() or "en"
    options = list(SUPPORTED_LANGUAGES.keys())
    try:
        cur_idx = options.index(current_lang)
    except ValueError:
        cur_idx = 0

    new_lang = st.selectbox(
        t("language_label"),
        options=options,
        index=cur_idx,
        format_func=lambda code: SUPPORTED_LANGUAGES.get(code, code),
        key="profile_lang_selector"
    )

    if new_lang != current_lang:
        try:
            client.update_user_language(new_lang)
            user["language"] = new_lang
            st.session_state["user"] = user
            set_language(new_lang)
            st.success("Language updated!")
            st.rerun()
        except Exception as e:
            st.error(f"Error changing language: {e}")
