import os
import sys

# Ensure project root is in sys.path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

import streamlit as st
import plotly.graph_objects as go
from dashboard.utils.api_client import get_api_client
from dashboard.utils.auth_ui import require_auth
from dashboard.utils.i18n import t

st.set_page_config(page_title="AI-Аналитик", page_icon="💬", layout="wide")

user = require_auth()
client = get_api_client()

active_set_id = user.get("active_set_id")

st.title(f"💬 {t('ai_analyst_title')}")
st.caption(f"{t('ai_analyst_subtitle')} (Gemini 2.5 Flash / Google AI Studio)")

if not user.get("gemini_api_key_valid"):
    st.warning("⚠️ Для работы интерактивного AI-аналитика требуется добавить ваш бесплатный **Gemini API Key** в разделе **«🔑 Профиль и API»**.")

# Chat history per active set
history_key = f"chat_history_{active_set_id}"
if history_key not in st.session_state:
    st.session_state[history_key] = [
        {
            "role": "assistant",
            "content": "Привет! Я твой YouTube AI-аналитик. Задай мне любой вопрос о твоих конкурентах в этом наборе каналов!\n\nНапример:\n- *Какие форматы роликов сейчас показывают максимальный рост?*\n- *Проанализируй заголовки лидеров по просмотрам.*\n- *Что мне снять на свой канал на основе успешных тем конкурентов?*",
            "chart": None
        }
    ]

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
        with st.spinner("Gemini анализирует контекст видео..."):
            try:
                response = client.ask_ai_analyst(
                    query=user_query,
                    set_id=active_set_id,
                    target_language=user.get("language", "ru")
                )
                answer = response.get("answer", "")
                findings = response.get("key_findings", [])
                plotly_spec = response.get("plotly_spec")

                findings_text = "\n".join([f"• {f}" for f in findings]) if findings else ""
                full_text = answer
                if findings_text:
                    full_text += f"\n\n**📌 Ключевые выводы:**\n{findings_text}"

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
                err = f"Ошибка: {e}"
                st.error(err)
                st.session_state[history_key].append({"role": "assistant", "content": err, "chart": None})
