import os
import sys

# Ensure project root is in sys.path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

import streamlit as st
import plotly.graph_objects as go
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

st.title(f"💬 {t('ai_analyst_title')}")
st.caption(f"{t('ai_analyst_subtitle')} (Gemini 3.8 Flash / Google AI Studio)")

if not user.get("gemini_api_key_valid"):
    st.warning(t("ai_gemini_key_required"))

# Chat history per active set
history_key = f"chat_history_{active_set_id}"
if history_key not in st.session_state:
    st.session_state[history_key] = []
elif (
    len(st.session_state[history_key]) == 1
    and st.session_state[history_key][0].get("role") == "assistant"
    and ("Hello! I am your YouTube AI Analyst" in st.session_state[history_key][0].get("content", "")
         or "Привет! Я ваш YouTube AI-Аналитик" in st.session_state[history_key][0].get("content", ""))
):
    # Reset legacy static greeting so it dynamically follows current language
    st.session_state[history_key] = []

# Display greeting dynamically in active interface language
with st.chat_message("assistant"):
    st.markdown(t("ai_welcome_message"))

# Display history
for msg in st.session_state[history_key]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("chart"):
            try:
                fig = go.Figure(msg["chart"])
                st.plotly_chart(fig, use_container_width=True)
            except Exception:
                pass

# User input
user_query = st.chat_input(t("ai_query_placeholder"))

if user_query:
    st.session_state[history_key].append({"role": "user", "content": user_query, "chart": None})
    with st.chat_message("user"):
        st.markdown(user_query)

    with st.chat_message("assistant"):
        with st.spinner(t("ai_analyzing_spinner")):
            try:
                active_lang = st.session_state.get("language", user.get("language", "en"))
                response = client.ask_ai_analyst(
                    query=user_query,
                    set_id=active_set_id,
                    target_language=active_lang
                )
                answer = response.get("answer", "")
                findings = response.get("key_findings", [])
                plotly_spec = response.get("plotly_spec")

                findings_text = "\n".join([f"• {f}" for f in findings]) if findings else ""
                full_text = answer
                if findings_text:
                    full_text += f"\n\n**{t('ai_key_takeaways')}**\n{findings_text}"

                st.markdown(full_text)
                if plotly_spec:
                    try:
                        fig = go.Figure(plotly_spec)
                        st.plotly_chart(fig, use_container_width=True)
                    except Exception:
                        pass

                st.session_state[history_key].append({
                    "role": "assistant",
                    "content": full_text,
                    "chart": plotly_spec
                })
            except Exception as e:
                err = f"Error: {e}"
                st.error(err)
                st.session_state[history_key].append({"role": "assistant", "content": err, "chart": None})

