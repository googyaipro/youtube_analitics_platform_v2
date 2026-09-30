import os
import sys
import time

# Ensure project root is in sys.path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

import streamlit as st
try:
    from dashboard.utils.api_client import get_api_client
    from dashboard.utils.auth_ui import require_auth
    from dashboard.utils.i18n import t, SUPPORTED_LANGUAGES, set_language, get_current_language, update_active_language
except ModuleNotFoundError:
    from utils.api_client import get_api_client
    from utils.auth_ui import require_auth
    from utils.i18n import t, SUPPORTED_LANGUAGES, set_language, get_current_language, update_active_language

user = require_auth()
client = get_api_client()

# Always fetch fresh profile on profile page to reflect real-time Telegram binding and key validation
try:
    fresh_user = client.get_me()
    st.session_state["user"] = fresh_user
    user = fresh_user
except Exception:
    pass

st.title(f"🔑 {t('profile_title')}")
st.caption(f"{t('profile_subtitle')}")

col_keys, col_tg = st.columns([3, 2])

# --- Column 1: API Keys (BYOK) ---
with col_keys:
    st.subheader(f"🛠️ {t('byok_title')}")
    st.info(t("byok_info"))

    # 1. YouTube Data API Key
    st.markdown(f"#### 1. {t('yt_key_label')}")
    yt_placeholder = f"•••••••••••••••• ({t('key_saved_replace_hint')})" if user.get("has_youtube_key") else "AIzaSy..."
    yt_input = st.text_input(
        t("yt_key_label"),
        type="password",
        placeholder=yt_placeholder,
        help=t("yt_key_help"),
        key="input_yt_key"
    )

    c_test_yt, c_status_yt = st.columns([1, 2])
    with c_test_yt:
        if st.button(t("test_yt_btn"), key="btn_test_yt"):
            key_to_test = yt_input.strip()
            if not key_to_test and not user.get("has_youtube_key"):
                st.warning(t("enter_key_to_test"))
            else:
                with st.spinner(t("testing_yt_key")):
                    try:
                        res = client.verify_key("youtube", key_to_test if key_to_test else "")
                        if res.get("is_valid") or res.get("valid"):
                            user["youtube_api_key_valid"] = True
                            user["has_youtube_key"] = True
                            st.session_state["user"] = user
                            st.success(f"✅ {res.get('message')}")
                        else:
                            st.error(f"❌ {res.get('message')}")
                    except Exception as e:
                        st.error(f"Error verifying key: {e}")

    with c_status_yt:
        if user.get("youtube_api_key_valid"):
            st.success(f"🟢 {t('key_valid')}")
        elif user.get("has_youtube_key"):
            st.warning(f"🟡 {t('key_pending')}")
        else:
            st.info(f"⚪ {t('key_not_configured')}")

    st.markdown("---")

    # 2. Gemini API Key
    st.markdown(f"#### 2. {t('gemini_key_label')}")
    gem_placeholder = f"•••••••••••••••• ({t('key_saved_replace_hint')})" if user.get("has_gemini_key") else "AIzaSy..."
    gemini_input = st.text_input(
        t("gemini_key_label"),
        type="password",
        placeholder=gem_placeholder,
        help=t("gemini_key_help"),
        key="input_gemini_key"
    )

    c_test_gem, c_status_gem = st.columns([1, 2])
    with c_test_gem:
        if st.button(t("test_gemini_btn"), key="btn_test_gemini"):
            key_to_test = gemini_input.strip()
            if not key_to_test and not user.get("has_gemini_key"):
                st.warning(t("enter_key_to_test"))
            else:
                with st.spinner(t("testing_gemini_key")):
                    try:
                        res = client.verify_key("gemini", key_to_test if key_to_test else "")
                        if res.get("is_valid") or res.get("valid"):
                            user["gemini_api_key_valid"] = True
                            user["has_gemini_key"] = True
                            st.session_state["user"] = user
                            st.success(f"✅ {res.get('message')}")
                        else:
                            st.error(f"❌ {res.get('message')}")
                    except Exception as e:
                        st.error(f"Error verifying key: {e}")

    with c_status_gem:
        if user.get("gemini_api_key_valid"):
            st.success(f"🟢 {t('key_valid')}")
        elif user.get("has_gemini_key"):
            st.warning(f"🟡 {t('key_pending')}")
        else:
            st.info(f"⚪ {t('key_not_configured')}")

    st.markdown("---")

    # Save button
    if st.button(f"💾 {t('save_keys_btn')}", type="primary", use_container_width=True):
        if not yt_input.strip() and not gemini_input.strip():
            st.warning(t("enter_one_key_error"))
        else:
            with st.spinner(t("saving_keys_spinner")):
                try:
                    res = client.update_user_keys(
                        youtube_key=yt_input.strip() if yt_input.strip() else None,
                        gemini_key=gemini_input.strip() if gemini_input.strip() else None
                    )
                    st.success(t("keys_saved_success"))
                    try:
                        st.session_state["user"] = client.get_me()
                    except Exception:
                        pass
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
        st.markdown(t("tg_features_desc"))
        c_test_tg, c_relink_tg = st.columns([1, 1])
        with c_test_tg:
            if st.button("🔔 " + t("test_telegram_btn", "Send Test Notification"), use_container_width=True):
                try:
                    res = client.send_telegram_test()
                    st.success(t("test_telegram_success", "Test message sent to your Telegram! Check your bot chat."))
                except Exception as e:
                    err_msg = str(e)
                    if hasattr(e, "response") and e.response is not None:
                        try:
                            err_msg = e.response.json().get("detail", err_msg)
                        except Exception:
                            pass
                    st.error(f"Error sending test message: {err_msg}")
        with c_relink_tg:
            if st.button("🔄 " + t("relink_btn", "Re-link Bot"), use_container_width=True):
                st.session_state.pop("tg_link_data", None)
                link_data = client.generate_telegram_link()
                st.session_state["tg_link_data"] = link_data
                st.rerun()
    else:
        st.warning(f"⚠️ {t('telegram_not_linked')}")
        st.markdown(t("tg_generate_instructions"))
        
        col_btn_link, col_btn_check = st.columns([2, 1])
        with col_btn_link:
            if st.button(f"🔗 {t('link_telegram_btn')}", use_container_width=True):
                try:
                    link_data = client.generate_telegram_link()
                    st.session_state["tg_link_data"] = link_data
                except Exception as e:
                    err_msg = str(e)
                    if hasattr(e, "response") and e.response is not None:
                        try:
                            err_msg = e.response.json().get("detail", err_msg)
                        except Exception:
                            pass
                    st.error(f"Error generating link: {err_msg}")

        with col_btn_check:
            if st.button("🔄 " + t("check_status_btn", "Check Status"), use_container_width=True):
                try:
                    fresh_user = client.get_me()
                    st.session_state["user"] = fresh_user
                except Exception:
                    pass
                st.rerun()

        if "tg_link_data" in st.session_state:
            link_data = st.session_state["tg_link_data"]
            link_url = link_data.get("link_url")
            link_code = link_data.get("code")
            if link_url:
                st.markdown(f"### [{t('tg_open_bot_link')}]({link_url})")
            if link_code:
                hint = t("tg_send_command_hint").replace("{code}", link_code)
                st.info(f"🔑 **{t('tg_binding_code_label')}** `{link_code}`\n\n{hint}")

    st.markdown("---")
    st.subheader(f"🌐 {t('language_label')}")
    current_lang = get_current_language()
    options = list(SUPPORTED_LANGUAGES.keys())

    # Pre-sync widget session state key so Streamlit never sees an outdated value
    if "profile_lang_selector" in st.session_state and st.session_state["profile_lang_selector"] != current_lang:
        st.session_state["profile_lang_selector"] = current_lang

    try:
        cur_idx = options.index(current_lang)
    except ValueError:
        cur_idx = 0

    def _on_profile_lang_change():
        val = st.session_state.get("profile_lang_selector")
        if val and val in SUPPORTED_LANGUAGES:
            update_active_language(val)

    st.selectbox(
        t("language_label"),
        options=options,
        index=cur_idx,
        format_func=lambda code: SUPPORTED_LANGUAGES.get(code, code),
        key="profile_lang_selector",
        on_change=_on_profile_lang_change
    )
