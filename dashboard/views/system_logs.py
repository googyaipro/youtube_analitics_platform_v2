import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

# Ensure project root is in sys.path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

import streamlit as st
import pandas as pd

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

st.title(f"📋 {t('logs_title')}")
st.caption(t("logs_subtitle"))

# Top action bar
col_title, col_refresh, col_clear = st.columns([5, 1.5, 1.5])
with col_refresh:
    if st.button(f"🔄 {t('btn_refresh')}", key="btn_refresh_logs", use_container_width=True):
        st.rerun()

with col_clear:
    if st.button(f"🗑️ {t('logs_clear_btn')}", key="btn_clear_logs", use_container_width=True):
        st.session_state["show_clear_confirm"] = True

if st.session_state.get("show_clear_confirm"):
    with st.container():
        st.warning(t("logs_clear_confirm_prompt"))
        c_yes, c_no = st.columns(2)
        with c_yes:
            if st.button(t("btn_confirm"), type="primary", use_container_width=True):
                try:
                    res = client.clear_logs(log_type="all")
                    st.success(f"✅ {res.get('message', 'Cleared')}")
                    st.session_state["show_clear_confirm"] = False
                    st.rerun()
                except Exception as ex:
                    st.error(f"Error clearing logs: {ex}")
        with c_no:
            if st.button(t("btn_cancel"), use_container_width=True):
                st.session_state["show_clear_confirm"] = False
                st.rerun()

# 1. AI Telemetry Statistics KPIs
try:
    stats = client.get_ai_stats()
except Exception as e:
    stats = {}

c_tot, c_succ, c_fall, c_err, c_lat = st.columns(5)
c_tot.metric(t("logs_kpi_total_ai"), stats.get("total_calls", 0))
c_succ.metric(t("logs_kpi_success"), stats.get("success_count", 0))
c_fall.metric(t("logs_kpi_fallbacks"), stats.get("fallback_count", 0))
c_err.metric(t("logs_kpi_errors"), stats.get("error_count", 0))
c_lat.metric(t("logs_kpi_avg_latency"), f"{stats.get('avg_latency_ms', 0)} ms")

st.markdown("---")

# Main tabs: AI Telemetry vs System Events vs Live Diagnostics
tab_ai, tab_sys, tab_live = st.tabs([
    f"🧠 {t('logs_tab_ai')}",
    f"⚙️ {t('logs_tab_system')}",
    f"🧪 {t('logs_tab_live_test')}"
])

# --- TAB 1: AI & LLM TELEMETRY ---
with tab_ai:
    st.subheader(f"🧠 {t('logs_ai_header')}")
    st.caption(t("logs_ai_desc"))

    # Filters
    f_c1, f_c2, f_c3, f_c4 = st.columns([2, 2, 3, 1.5])
    with f_c1:
        status_opts = ["ALL", "SUCCESS", "ERROR", "FALLBACK_RULE_BASED", "PARSE_ERROR", "PARSE_ERROR_RECOVERED"]
        selected_status = st.selectbox(t("logs_filter_status"), status_opts, key="ai_log_status")
    with f_c2:
        op_opts = ["ALL", "explain_video", "daily_digest", "ask_analyst", "verify_key"]
        selected_op = st.selectbox(t("logs_filter_operation"), op_opts, key="ai_log_op")
    with f_c3:
        search_query = st.text_input(t("logs_search_placeholder"), placeholder="Video title, prompt, error...", key="ai_log_search")
    with f_c4:
        limit_val = st.selectbox(t("logs_limit"), [20, 50, 100], index=1, key="ai_log_limit")

    try:
        ai_logs = client.get_ai_logs(
            limit=limit_val,
            status=selected_status,
            operation=selected_op,
            search=search_query
        )
    except Exception as ex:
        st.error(f"Error loading AI logs: {ex}")
        ai_logs = []

    if not ai_logs:
        st.info(t("logs_empty_ai"))
    else:
        st.write(f"**{t('logs_found')}:** {len(ai_logs)}")

        for log in ai_logs:
            status = log.get("status", "UNKNOWN")
            if status == "SUCCESS":
                badge = "🟢 SUCCESS"
            elif status == "PARSE_ERROR_RECOVERED":
                badge = "🟡 RECOVERED"
            elif status == "FALLBACK_RULE_BASED":
                badge = "🟠 FALLBACK"
            elif status == "PARSE_ERROR":
                badge = "🔴 PARSE ERROR"
            else:
                badge = "🔴 ERROR"

            created = log.get("created_at", "")[:19].replace("T", " ")
            op = log.get("operation", "")
            target = log.get("target_title") or log.get("target_id") or "N/A"
            target_short = (target[:45] + "...") if len(target) > 45 else target
            model = log.get("model", "gemini-flash-latest")
            lat = log.get("latency_ms", 0)
            user_lbl = f" | 👤 {log.get('user_email')}" if log.get("user_email") and user.get("is_admin") else ""

            exp_label = f"{badge} | {created} | [{op}] {target_short} | 🤖 `{model}` ({lat} ms){user_lbl}"

            with st.expander(exp_label):
                m_c1, m_c2, m_c3, m_c4 = st.columns(4)
                m_c1.markdown(f"**Operation:** `{op}`")
                m_c2.markdown(f"**Model:** `{model}`")
                m_c3.markdown(f"**Latency:** `{lat} ms`")
                m_c4.markdown(f"**HTTP Status:** `{log.get('http_status') or '--'}`")

                if log.get("target_title"):
                    st.markdown(f"**Target / Context:** {log.get('target_title')}")
                if log.get("target_id"):
                    st.caption(f"Target ID: `{log.get('target_id')}`")

                # Show error / fallback reason clearly
                if log.get("fallback_reason"):
                    st.warning(f"⚠️ **Fallback / Parsing Note:** {log.get('fallback_reason')}")
                if log.get("error_message"):
                    st.error(f"❌ **Error Message:** {log.get('error_message')}")

                # Prompt and Response tabs
                v_tab_p, v_tab_r, v_tab_parsed = st.tabs([
                    f"📝 {t('logs_view_prompt')}",
                    f"📥 {t('logs_view_raw')}",
                    f"📊 {t('logs_view_parsed')}"
                ])

                with v_tab_p:
                    prompt_txt = log.get("prompt")
                    if prompt_txt:
                        st.code(prompt_txt, language="markdown")
                    else:
                        st.caption("No prompt recorded.")

                with v_tab_r:
                    raw_txt = log.get("raw_response")
                    if raw_txt:
                        st.code(raw_txt, language="json" if raw_txt.strip().startswith("{") else "text")
                    else:
                        st.caption("No raw response recorded.")

                with v_tab_parsed:
                    parsed_txt = log.get("parsed_output")
                    if parsed_txt:
                        try:
                            import json
                            st.json(json.loads(parsed_txt))
                        except Exception:
                            st.text(parsed_txt)
                    else:
                        st.caption("No structured output recorded.")

# --- TAB 2: SYSTEM EVENT LOGS ---
with tab_sys:
    st.subheader(f"⚙️ {t('logs_sys_header')}")
    st.caption(t("logs_sys_desc"))

    s_c1, s_c2, s_c3, s_c4 = st.columns([2, 2, 3, 1.5])
    with s_c1:
        cat_opts = ["ALL", "telegram", "scheduler", "sync", "auth", "system"]
        selected_cat = st.selectbox(t("logs_filter_category"), cat_opts, key="sys_cat")
    with s_c2:
        lvl_opts = ["ALL", "INFO", "WARNING", "ERROR", "CRITICAL"]
        selected_lvl = st.selectbox(t("logs_filter_level"), lvl_opts, key="sys_lvl")
    with s_c3:
        sys_search = st.text_input(t("logs_search_placeholder"), placeholder="Action, message, email...", key="sys_search")
    with s_c4:
        sys_limit = st.selectbox(t("logs_limit"), [20, 50, 100], index=1, key="sys_limit")

    try:
        sys_logs = client.get_system_logs(
            limit=sys_limit,
            category=selected_cat,
            level=selected_lvl,
            search=sys_search
        )
    except Exception as ex:
        st.error(f"Error loading system logs: {ex}")
        sys_logs = []

    if not sys_logs:
        st.info(t("logs_empty_sys"))
    else:
        st.write(f"**{t('logs_found')}:** {len(sys_logs)}")

        for s_log in sys_logs:
            lvl = s_log.get("level", "INFO")
            if lvl == "ERROR" or lvl == "CRITICAL":
                lvl_badge = "🔴 ERROR"
            elif lvl == "WARNING":
                lvl_badge = "🟡 WARNING"
            else:
                lvl_badge = "🟢 INFO"

            created = s_log.get("created_at", "")[:19].replace("T", " ")
            cat = s_log.get("category", "")
            act = s_log.get("action", "")
            msg = s_log.get("message", "")
            u_email = f" | 👤 {s_log.get('user_email')}" if s_log.get("user_email") and user.get("is_admin") else ""

            exp_title = f"{lvl_badge} | {created} | [{cat.upper()}] `{act}`: {msg[:60]}{u_email}"

            with st.expander(exp_title):
                st.markdown(f"**Timestamp:** `{created}` | **Category:** `{cat}` | **Action:** `{act}`")
                st.markdown(f"**Message:** {msg}")
                if s_log.get("details"):
                    st.markdown("**Payload / Trace Details:**")
                    try:
                        import json
                        st.json(json.loads(s_log["details"]))
                    except Exception:
                        st.code(s_log["details"], language="text")

# --- TAB 3: LIVE AI DIAGNOSTICS ---
with tab_live:
    st.subheader(f"🧪 {t('logs_live_header')}")
    st.caption(t("logs_live_desc"))

    with st.form("live_ai_test_form"):
        test_prompt = st.text_area(
            t("logs_test_prompt_label"),
            value="Break down why a YouTube video about 'Claude 3.7 vs Opus 5.5' went viral. Return a 3-bullet forensic strategy diagnostic.",
            height=120
        )
        submit_test = st.form_submit_button(f"⚡ {t('logs_test_btn')}", type="primary", use_container_width=True)

        if submit_test:
            with st.spinner(t("ai_analyzing_spinner")):
                try:
                    res = client.ask_analyst(query=test_prompt)
                    st.success("✅ " + t("logs_test_success"))
                    st.markdown("### 🎯 Результат ответа модели:")
                    if isinstance(res, dict):
                        st.write(res.get("answer", ""))
                        if res.get("key_findings"):
                            st.write("**Key findings:**", res.get("key_findings"))
                    else:
                        st.write(res)
                    st.info("💡 Запрос и полный ответ только что зафиксированы в журнале телеметрии (вкладка 🧠 AI Телеметрия).")
                except Exception as ex:
                    st.error(f"❌ Ошибка вызова: {ex}")
