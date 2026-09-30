import os
import sys

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

st.title(f"⚙️ {t('nav_channel_sets')}")
st.caption(t("app_tagline"))

channel_sets = client.get_channel_sets()
tab_sets, tab_channels = st.tabs([f"📁 {t('nav_channel_sets')}", f"📺 {t('kpi_channels')}"])

# --- TAB 1: Channel Sets & Scheduler ---
with tab_sets:
    col_list, col_create = st.columns([3, 2])

    with col_list:
        st.subheader(f"📁 {t('channel_sets_header')}")
        if not channel_sets:
            st.info(t("no_channel_sets_yet"))
        else:
            for s in channel_sets:
                is_active = s.get("id") == user.get("active_set_id")
                active_badge = f" 🟢 ({t('set_active_btn')})" if is_active else ""
                
                with st.expander(f"📁 {s['name']}{active_badge}"):
                    st.markdown(f"**{t('desc_label')}:** {s.get('description') or '—'}")
                    st.markdown(f"**⏰ {t('digest_time_label')}:** `{s.get('schedule_time', '12:00')}` ({s.get('schedule_timezone', 'UTC')})")
                    st.markdown(f"**📅 {t('days_label')}:** `{s.get('schedule_days', 'mon,tue,wed,thu,fri')}`")
                    st.markdown(f"**{t('scheduled_dispatch_label')}:** {'✅ ' + t('schedule_enabled') if s.get('schedule_enabled') else '❌'}")

                    c_act, c_del = st.columns(2)
                    with c_act:
                        if not is_active:
                            if st.button(t("set_active_btn"), key=f"act_{s['id']}", use_container_width=True):
                                client.activate_channel_set(s["id"])
                                user["active_set_id"] = s["id"]
                                st.session_state["user"] = user
                                st.success(f"Set '{s['name']}' activated!")
                                st.rerun()
                    with c_del:
                        if len(channel_sets) > 1:
                            if st.button(t("delete_set_btn"), key=f"del_{s['id']}", type="secondary", use_container_width=True):
                                client.delete_channel_set(s["id"])
                                st.success("Set deleted.")
                                st.rerun()

    with col_create:
        st.subheader(f"➕ {t('create_set')}")
        with st.form("create_set_form"):
            new_name = st.text_input(f"{t('set_name')} *", placeholder="e.g. AI Tech & Tools")
            new_desc = st.text_area(t("set_description"), placeholder="Top 10 AI video creators")
            
            c_time, c_tz = st.columns(2)
            with c_time:
                new_time = st.text_input(t("schedule_time"), value="12:00")
            with c_tz:
                new_tz = st.selectbox(
                    t("schedule_timezone"),
                    options=["America/New_York", "UTC", "Europe/London", "Europe/Berlin", "Europe/Helsinki", "Europe/Moscow", "Asia/Tbilisi"],
                    index=0
                )

            new_days = st.multiselect(
                t("schedule_days"),
                options=["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
                default=["mon", "tue", "wed", "thu", "fri"]
            )
            new_enabled = st.checkbox(t("schedule_enabled"), value=True)

            submit_set = st.form_submit_button(t("create_set"), use_container_width=True)

            if submit_set:
                if not new_name.strip():
                    st.error(t("enter_set_name_error"))
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
                        st.success(f"Set '{created['name']}' created successfully!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error creating set: {e}")


# --- TAB 2: Channels Management ---
with tab_channels:
    if not channel_sets:
        st.warning(t("no_channels"))
    else:
        set_map = {s["name"]: s["id"] for s in channel_sets}
        active_set_id = user.get("active_set_id")
        def_idx = 0
        for idx, (name, s_id) in enumerate(set_map.items()):
            if s_id == active_set_id:
                def_idx = idx
                break

        selected_set_name = st.selectbox(t("select_set"), options=list(set_map.keys()), index=def_idx)
        selected_set_id = set_map[selected_set_name]

        st.markdown("---")
        st.subheader(f"➕ {t('add_channel')}")
        with st.form("add_ch_form"):
            col_in, col_btn = st.columns([3, 1])
            with col_in:
                channel_input = st.text_input(
                    "Handle, URL, or Channel ID",
                    placeholder="@mkbhd or https://www.youtube.com/@mkbhd",
                    help=t("channel_input_help")
                )
            with col_btn:
                st.write("")
                add_sub = st.form_submit_button(t("add_channel_btn"), use_container_width=True)

            if add_sub:
                if not channel_input.strip():
                    st.error("Please enter channel handle or link.")
                else:
                    with st.spinner("Fetching channel via YouTube API..."):
                        try:
                            res = client.add_channel(channel_input.strip(), set_id=selected_set_id)
                            st.success(f"{t('channel_added')} ({res.get('title')})")
                            st.rerun()
                        except Exception as e:
                            err_msg = str(e)
                            if hasattr(e, "response") and e.response is not None:
                                try:
                                    err_msg = e.response.json().get("detail", err_msg)
                                except Exception:
                                    pass
                            st.error(f"Error adding channel: {err_msg}")

        st.markdown("---")
        st.subheader(f"📋 {selected_set_name} — Channels")
        channels = client.get_channels(set_id=selected_set_id)

        if not channels:
            st.info(t("no_channels"))
        else:
            df_ch = pd.DataFrame(channels)
            df_ch["youtube_url"] = df_ch.apply(
                lambda r: f"https://www.youtube.com/{r['custom_url']}" if r.get("custom_url") and str(r["custom_url"]).startswith("@") else f"https://www.youtube.com/channel/{r['channel_id']}",
                axis=1
            )
            col_map = {
                "title": t("channel_title"),
                "custom_url": "Handle",
                "subscriber_count": "Subscribers",
                "view_count": t("views"),
                "video_count": "Total Videos",
                "youtube_url": "Link"
            }
            avail = [c for c in col_map.keys() if c in df_ch.columns]
            df_show = df_ch[avail].rename(columns=col_map)
            st.dataframe(
                df_show,
                column_config={
                    "Link": st.column_config.LinkColumn("YouTube", display_text="🔗 Channel"),
                    "Subscribers": st.column_config.NumberColumn("Subscribers", format="%d"),
                    t("views"): st.column_config.NumberColumn(t("views"), format="%d"),
                    "Total Videos": st.column_config.NumberColumn("Videos", format="%d"),
                },
                hide_index=True,
                use_container_width=True
            )

            # Delete channel section
            st.markdown("##### 🗑️ Remove Channel")
            c_options = {f"{c['title']} ({c.get('custom_url') or c['channel_id']})": c['id'] for c in channels}
            target_to_del = st.selectbox("Select channel to remove:", options=list(c_options.keys()))
            target_id = c_options[target_to_del]

            if st.button("Delete Channel", type="secondary"):
                try:
                    client.delete_channel(target_id, set_id=selected_set_id)
                    st.success(t("channel_deleted"))
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
