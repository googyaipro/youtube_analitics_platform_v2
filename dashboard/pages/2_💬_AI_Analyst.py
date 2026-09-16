import streamlit as st
import plotly.graph_objects as go
from utils.api_client import APIClient

st.set_page_config(page_title="AI-Аналитик (Интерактивный чат)", page_icon="💬", layout="wide")
st.title("💬 AI-Аналитик YouTube (Gemini 3.5 Flash)")
st.caption("Интеллектуальный анализ каналов, выявление аномалий и генерация интерактивных графиков Plotly.")

client = APIClient()

# Session state for chat history
if "chat_history" not in st.session_state:
    st.session_state.chat_history = [
        {
            "role": "assistant",
            "content": "Привет! Я твой YouTube AI-аналитик. Спроси меня, например:\n- *Сравни вовлеченность и просмотры видео @GoogleCloud*\n- *Какое видео набрало больше всего просмотров у @MKBHD?*",
            "chart": None
        }
    ]

# Display past messages
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("chart"):
            fig = go.Figure(msg["chart"])
            st.plotly_chart(fig, use_container_width=True)

# User input
user_query = st.chat_input("Задайте вопрос по аналитике каналов...")

if user_query:
    # Append user message
    st.session_state.chat_history.append({"role": "user", "content": user_query, "chart": None})
    with st.chat_message("user"):
        st.markdown(user_query)

    # Call AI Analyst backend
    with st.chat_message("assistant"):
        with st.spinner("Gemini анализирует видео и строит график..."):
            response = client.ask_ai_analyst(user_query)

            if "error" in response and not response.get("summary_text"):
                error_msg = f"⚠️ Ошибка: {response['error']}"
                st.error(error_msg)
                st.session_state.chat_history.append({"role": "assistant", "content": error_msg, "chart": None})
            else:
                summary = response.get("summary_text", "")
                findings = response.get("key_findings", [])
                plotly_spec = response.get("plotly_spec")

                # Compose answer
                findings_text = "\n".join([f"- {f}" for f in findings]) if findings else ""
                full_text = f"{summary}\n\n**Ключевые инсайты:**\n{findings_text}"
                st.markdown(full_text)

                if plotly_spec:
                    fig = go.Figure(plotly_spec)
                    st.plotly_chart(fig, use_container_width=True)

                st.session_state.chat_history.append({
                    "role": "assistant",
                    "content": full_text,
                    "chart": plotly_spec
                })
