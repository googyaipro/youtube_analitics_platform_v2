from typing import Optional
import streamlit as st
try:
    from dashboard.utils.api_client import get_api_client
    from dashboard.utils.i18n import t, get_current_language, set_language, render_language_selector
except ModuleNotFoundError:
    from utils.api_client import get_api_client
    from utils.i18n import t, get_current_language, set_language, render_language_selector


def render_auth_modal():
    """Render Login / Registration tabbed card."""
    client = get_api_client()

    st.markdown(f"### 🔐 {t('login')} / {t('register')}")
    st.info(t("auth_required"))

    tab_login, tab_register = st.tabs([t("login"), t("register")])

    with tab_login:
        with st.form("login_form"):
            email = st.text_input(t("email"), placeholder="user@example.com", key="login_email")
            password = st.text_input(t("password"), type="password", key="login_pwd")
            submit = st.form_submit_button(t("login_btn"), use_container_width=True)

            if submit:
                if not email or not password:
                    st.error("Please enter email and password.")
                else:
                    try:
                        resp = client.login(email.strip(), password)
                        st.session_state["access_token"] = resp["access_token"]
                        user = resp.get("user", {})
                        st.session_state["user"] = user
                        if user.get("language"):
                            set_language(user["language"])
                        st.success(t("auth_success"))
                        st.rerun()
                    except Exception as e:
                        err_msg = str(e)
                        if hasattr(e, "response") and e.response is not None:
                            try:
                                err_msg = e.response.json().get("detail", err_msg)
                            except Exception:
                                pass
                        st.error(f"{t('auth_error')}: {err_msg}")

    with tab_register:
        with st.form("register_form"):
            full_name = st.text_input(t("full_name"), placeholder="Alex Developer", key="reg_name")
            reg_email = st.text_input(t("email"), placeholder="user@example.com", key="reg_email")
            reg_password = st.text_input(t("password"), type="password", help="At least 6 characters", key="reg_pwd")
            submit_reg = st.form_submit_button(t("register_btn"), use_container_width=True)

            if submit_reg:
                if not reg_email or not reg_password:
                    st.error("Please fill in email and password.")
                elif len(reg_password) < 6:
                    st.error("Password must be at least 6 characters.")
                else:
                    try:
                        current_lang = get_current_language()
                        resp = client.register(
                            email=reg_email.strip(),
                            password=reg_password,
                            full_name=full_name.strip() if full_name else None,
                            language=current_lang
                        )
                        st.session_state["access_token"] = resp["access_token"]
                        user = resp.get("user", {})
                        st.session_state["user"] = user
                        st.success(t("auth_success"))
                        st.rerun()
                    except Exception as e:
                        err_msg = str(e)
                        if hasattr(e, "response") and e.response is not None:
                            try:
                                err_msg = e.response.json().get("detail", err_msg)
                            except Exception:
                                pass
                        st.error(f"{t('auth_error')}: {err_msg}")


def require_auth() -> dict:
    """
    Guard function: verifies user is authenticated.
    If not, renders auth card and halts page execution.
    """
    token = st.session_state.get("access_token")
    if not token:
        # Render language selector on auth screen too!
        render_language_selector(sidebar=True)
        render_auth_modal()
        st.stop()

    # User is logged in
    user = st.session_state.get("user")
    if not user:
        try:
            client = get_api_client()
            user = client.get_me()
            st.session_state["user"] = user
        except Exception:
            # Token expired or invalid
            st.session_state.pop("access_token", None)
            st.session_state.pop("user", None)
            st.rerun()

    # Render sidebar profile info & logout
    with st.sidebar:
        st.markdown(f"👤 **{user.get('email', 'User')}**")
        if user.get("full_name"):
            st.caption(user.get("full_name"))

        render_language_selector(sidebar=False)

        if st.button(f"🚪 {t('logout')}", use_container_width=True):
            st.session_state.pop("access_token", None)
            st.session_state.pop("user", None)
            st.session_state.pop("active_set_id", None)
            st.rerun()

        st.markdown("---")

    return user
