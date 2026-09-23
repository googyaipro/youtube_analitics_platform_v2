import os
import sys

# Ensure project root is in sys.path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

import streamlit as st
import pandas as pd
from dashboard.utils.api_client import get_api_client
from dashboard.utils.auth_ui import require_auth
from dashboard.utils.i18n import t

st.set_page_config(page_title="Наборы каналов и планировщик", page_icon="⚙️", layout="wide")

user = require_auth()
client = get_api_client()

st.title("⚙️ Наборы каналов и персональный планировщик")
st.caption("Создавайте независимые рабочие пространства (например: Tech, Gaming, Crypto), настраивайте расписание AI-дайджестов и управляйте каналами конкурентов.")

channel_sets = client.get_channel_sets()
tab_sets, tab_channels = st.tabs(["📁 Управление наборами и расписанием", "📺 Каналы в выбранном наборе"])

# --- TAB 1: Channel Sets & Scheduler ---
with tab_sets:
    col_list, col_create = st.columns([3, 2])

    with col_list:
        st.subheader("Ваши наборы каналов")
        if not channel_sets:
            st.info("У вас пока нет созданных наборов каналов.")
        else:
            for s in channel_sets:
                is_active = s.get("id") == user.get("active_set_id")
                active_badge = " 🟢 (Активен)" if is_active else ""
                
                with st.expander(f"📁 {s['name']}{active_badge}"):
                    st.markdown(f"**Описание:** {s.get('description') or 'Нет описания'}")
                    st.markdown(f"**⏰ Расписание дайджеста:** `{s.get('schedule_time', '12:00')}` ({s.get('schedule_timezone', 'UTC')})")
                    st.markdown(f"**📅 Дни отправки:** `{s.get('schedule_days', 'mon,tue,wed,thu,fri')}`")
                    st.markdown(f"**Авто-отправка:** {'✅ Включена' if s.get('schedule_enabled') else '❌ Выключена'}")

                    c_act, c_del = st.columns(2)
                    with c_act:
                        if not is_active:
                            if st.button("Сделать активным", key=f"act_{s['id']}", use_container_width=True):
                                client.activate_channel_set(s["id"])
                                user["active_set_id"] = s["id"]
                                st.session_state["user"] = user
                                st.success(f"Набор «{s['name']}» выбран активным!")
                                st.rerun()
                    with c_del:
                        if len(channel_sets) > 1:
                            if st.button("🗑️ Удалить набор", key=f"del_{s['id']}", type="secondary", use_container_width=True):
                                client.delete_channel_set(s["id"])
                                st.success("Набор удален.")
                                st.rerun()

    with col_create:
        st.subheader("➕ Создать новый набор")
        with st.form("create_set_form"):
            new_name = st.text_input("Название набора *", placeholder="Например: Crypto & DeFi")
            new_desc = st.text_area("Описание (опционально)", placeholder="Мониторинг топ-10 крипто-каналов")
            
            c_time, c_tz = st.columns(2)
            with c_time:
                new_time = st.text_input("Время отправки (HH:MM)", value="12:00")
            with c_tz:
                new_tz = st.selectbox(
                    "Часовой пояс",
                    options=["Europe/Helsinki", "Europe/Berlin", "Europe/Moscow", "Asia/Tbilisi", "UTC", "America/New_York"],
                    index=0
                )

            new_days = st.multiselect(
                "Дни недели для дайджеста",
                options=["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
                default=["mon", "tue", "wed", "thu", "fri"]
            )
            new_enabled = st.checkbox("Включить расписание по умолчанию", value=True)

            submit_set = st.form_submit_button("Создать набор", use_container_width=True)

            if submit_set:
                if not new_name.strip():
                    st.error("Укажите название набора.")
                else:
                    try:
                        created = client.create_channel_set({
                            "name": new_name.strip(),
                            "description": new_desc.strip() if new_desc else None,
                            "schedule_time": new_time.strip(),
                            "schedule_timezone": new_tz,
                            "schedule_days": ",".join(new_days),
                            "schedule_enabled": new_enabled
                        })
                        st.success(f"Набор «{created['name']}» успешно создан!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Ошибка создания: {e}")


# --- TAB 2: Channels Management ---
with tab_channels:
    if not channel_sets:
        st.warning("Сначала создайте хотя бы один набор каналов.")
    else:
        set_map = {s["name"]: s["id"] for s in channel_sets}
        active_set_id = user.get("active_set_id")
        def_idx = 0
        for idx, (name, s_id) in enumerate(set_map.items()):
            if s_id == active_set_id:
                def_idx = idx
                break

        selected_set_name = st.selectbox("Выберите набор каналов для редактирования:", options=list(set_map.keys()), index=def_idx)
        selected_set_id = set_map[selected_set_name]

        st.markdown("---")
        st.subheader("➕ Добавить канал в набор")
        with st.form("add_ch_form"):
            col_in, col_btn = st.columns([3, 1])
            with col_in:
                channel_input = st.text_input(
                    "Handle или URL YouTube-канала",
                    placeholder="Например: @mkbhd или https://www.youtube.com/@mkbhd",
                    help="Поддерживаются handles (@...), полные ссылки и ID каналов"
                )
            with col_btn:
                st.write("")
                add_sub = st.form_submit_button("Добавить канал", use_container_width=True)

            if add_sub:
                if not channel_input.strip():
                    st.error("Введите handle или ссылку на канал.")
                else:
                    with st.spinner("Загрузка данных канала через YouTube API..."):
                        try:
                            res = client.add_channel(channel_input.strip(), set_id=selected_set_id)
                            st.success(f"Канал **{res.get('title')}** успешно добавлен в набор!")
                            st.rerun()
                        except Exception as e:
                            err_msg = str(e)
                            if hasattr(e, "response") and e.response is not None:
                                try:
                                    err_msg = e.response.json().get("detail", err_msg)
                                except Exception:
                                    pass
                            st.error(f"Не удалось добавить канал: {err_msg}")

        st.markdown("---")
        st.subheader(f"📋 Каналы в наборе «{selected_set_name}»")
        channels = client.get_channels(set_id=selected_set_id)

        if not channels:
            st.info("В этом наборе пока нет добавленных каналов.")
        else:
            df_ch = pd.DataFrame(channels)
            df_ch["youtube_url"] = df_ch.apply(
                lambda r: f"https://www.youtube.com/{r['custom_url']}" if r.get("custom_url") and str(r["custom_url"]).startswith("@") else f"https://www.youtube.com/channel/{r['channel_id']}",
                axis=1
            )
            col_map = {
                "title": "Название канала",
                "custom_url": "Handle",
                "subscriber_count": "Подписчики",
                "view_count": "Просмотры",
                "video_count": "Всего видео",
                "youtube_url": "Ссылка"
            }
            avail = [c for c in col_map.keys() if c in df_ch.columns]
            df_show = df_ch[avail].rename(columns=col_map)
            st.dataframe(
                df_show,
                column_config={
                    "Ссылка": st.column_config.LinkColumn("YouTube", display_text="🔗 Открыть"),
                    "Подписчики": st.column_config.NumberColumn("Подписчики", format="%d"),
                    "Просмотры": st.column_config.NumberColumn("Просмотры", format="%d"),
                    "Всего видео": st.column_config.NumberColumn("Видео", format="%d"),
                },
                hide_index=True,
                use_container_width=True
            )

            # Delete channel section
            st.markdown("##### 🗑️ Удалить канал из набора")
            c_options = {f"{c['title']} ({c.get('custom_url') or c['channel_id']})": c['id'] for c in channels}
            target_to_del = st.selectbox("Выберите канал для удаления:", options=list(c_options.keys()))
            target_id = c_options[target_to_del]

            if st.button("Удалить выбранный канал", type="secondary"):
                try:
                    client.delete_channel(target_id, set_id=selected_set_id)
                    st.success(f"Канал удален из набора!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Ошибка удаления: {e}")
