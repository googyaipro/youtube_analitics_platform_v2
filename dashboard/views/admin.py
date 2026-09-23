import os
import sys
from datetime import datetime

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

st.title(f"👑 {t('admin_title')}")
st.caption(t("admin_subtitle"))

# --- Gate: Check if user is administrator ---
if not user.get("is_admin"):
    st.warning("🔒 You are not currently an Administrator.")
    
    with st.container():
        st.markdown(f"### 🔑 {t('admin_claim_title')}")
        st.write(t("admin_claim_desc"))
        
        with st.form("claim_admin_form"):
            secret_input = st.text_input(
                "Admin Secret Key",
                type="password",
                placeholder="Enter ADMIN_SECRET...",
                help="Configured via ADMIN_SECRET environment variable (default: yap_admin_secret_2026)"
            )
            claim_btn = st.form_submit_button(f"🚀 {t('admin_claim_btn')}", type="primary", use_container_width=True)
            
            if claim_btn:
                if not secret_input.strip():
                    st.error("Please enter the admin secret key.")
                else:
                    try:
                        res = client.claim_admin(secret_input.strip())
                        user["is_admin"] = True
                        st.session_state["user"] = user
                        st.success("🎉 " + res.get("message", "Administrator privileges granted!"))
                        st.rerun()
                    except Exception as e:
                        err_msg = str(e)
                        if hasattr(e, "response") and e.response is not None:
                            try:
                                err_msg = e.response.json().get("detail", err_msg)
                            except Exception:
                                pass
                        st.error(f"Authorization failed: {err_msg}")
    st.stop()


# --- Admin Authorized Dashboard ---
col_head, col_refresh = st.columns([4, 1])
with col_refresh:
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.rerun()

# 1. Statistics KPIs
try:
    stats = client.get_admin_stats()
except Exception as e:
    st.error(f"Error fetching stats: {e}")
    stats = {}

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric(t("admin_stats_users"), stats.get("total_users", 0))
c2.metric(t("admin_stats_active"), stats.get("active_users", 0))
c3.metric(t("admin_stats_blocked"), stats.get("blocked_users", 0))
c4.metric(t("admin_stats_admins"), stats.get("admin_users", 0))
c5.metric(t("admin_stats_sets"), stats.get("total_channel_sets", 0))
c6.metric(t("admin_stats_channels"), stats.get("total_channels", 0))

st.markdown("---")

# 1.1 Telegram Bot & Webhook Diagnostics
with st.expander("🤖 Telegram Bot & Webhook Diagnostics", expanded=True):
    try:
        tg_status = client.get_admin_telegram_status()
        bot_cfg = tg_status.get("bot_token_configured")
        bot_info = tg_status.get("bot_info") or {}
        wh_info = tg_status.get("webhook_info") or {}
        expected_url = tg_status.get("expected_webhook_url")
        current_url = wh_info.get("url", "")
        
        tc1, tc2, tc3 = st.columns(3)
        with tc1:
            bot_label = f"@{bot_info.get('username')}" if bot_info.get("username") else ("Configured" if bot_cfg else "Not Configured")
            tc1.metric("Bot Status", bot_label)
        with tc2:
            wh_label = "🟢 Connected" if (current_url and current_url == expected_url) else "⚠️ Needs Sync"
            tc2.metric("Webhook Status", wh_label)
        with tc3:
            tc3.metric("Pending Updates", wh_info.get("pending_update_count", 0))

        st.markdown(f"**Registered Webhook URL:** `{current_url or 'None (Not registered with Telegram)'}`")
        st.markdown(f"**Expected Webhook URL:** `{expected_url}`")
        if wh_info.get("last_error_message"):
            st.error(f"⚠️ Last Telegram Error: {wh_info.get('last_error_message')}")

        if st.button("🔄 Sync / Re-register Telegram Webhook Now", type="secondary", use_container_width=True):
            res = client.setup_admin_telegram_webhook()
            st.success("Telegram Webhook successfully re-registered!")
            st.rerun()
    except Exception as e:
        st.error(f"Error checking Telegram status: {e}")

st.markdown("---")

# 2. Users Management
st.subheader("👥 User Accounts & Access Control")

try:
    all_users = client.get_admin_users()
except Exception as e:
    st.error(f"Error loading users: {e}")
    all_users = []

col_search, col_filter = st.columns([3, 2])
with col_search:
    search_q = st.text_input("🔍 Search users by email or name:", placeholder="alex@example.com").strip().lower()

with col_filter:
    filter_role = st.selectbox("Status Filter:", ["All", "Active Only", "Blocked Only", "Admins Only"])

# Filter logic
filtered_users = []
for u in all_users:
    u_email = (u.get("email") or "").lower()
    u_name = (u.get("full_name") or "").lower()
    
    if search_q and (search_q not in u_email and search_q not in u_name):
        continue
    
    if filter_role == "Active Only" and not u.get("is_active"):
        continue
    if filter_role == "Blocked Only" and u.get("is_active"):
        continue
    if filter_role == "Admins Only" and not u.get("is_admin"):
        continue
    
    filtered_users.append(u)

st.caption(f"Showing **{len(filtered_users)}** of **{len(all_users)}** user accounts.")

if not filtered_users:
    st.info("No users match the criteria.")
else:
    for u in filtered_users:
        is_self = u["id"] == user.get("id")
        
        status_badge = "🟢 Active" if u.get("is_active") else "🔴 BLOCKED"
        role_badge = "👑 Admin" if u.get("is_admin") else "👤 User"
        self_badge = " *(You)*" if is_self else ""
        
        card_title = f"{u['email']} — {role_badge} | {status_badge}{self_badge}"
        
        with st.expander(card_title, expanded=False):
            col_info, col_actions = st.columns([3, 2])
            
            with col_info:
                st.markdown(f"**User ID:** `{u['id']}`")
                st.markdown(f"**Full Name:** {u.get('full_name') or 'Not specified'}")
                st.markdown(f"**Language:** `{u.get('language')}`")
                st.markdown(f"**Registered:** `{str(u.get('created_at'))[:19]}`")
                st.markdown(f"**Channel Sets:** {u.get('channel_sets_count', 0)} | **Channels Monitored:** {u.get('channels_count', 0)}")
                
                # BYOK & Telegram status
                yt_status = "✅ Configured" if u.get("has_youtube_key") else "❌ None"
                gem_status = "✅ Configured" if u.get("has_gemini_key") else "❌ None"
                tg_status = f"✅ Linked (`{u.get('telegram_chat_id')}`)" if u.get("telegram_chat_id") else "❌ Not linked"
                st.markdown(f"**YouTube Key:** {yt_status} | **Gemini Key:** {gem_status}")
                st.markdown(f"**Telegram Bot:** {tg_status}")

            with col_actions:
                st.markdown("##### ⚡ Quick Actions")
                
                if is_self:
                    st.info("You cannot modify your own administrator account.")
                else:
                    # 1. Block / Unblock Toggle
                    if u.get("is_active"):
                        if st.button(f"🚫 {t('admin_block_btn')}", key=f"blk_{u['id']}", type="secondary", use_container_width=True):
                            try:
                                res = client.toggle_user_active(u["id"])
                                st.warning(res.get("message", "User blocked."))
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error: {e}")
                    else:
                        if st.button(f"🟢 {t('admin_unblock_btn')}", key=f"unblk_{u['id']}", type="primary", use_container_width=True):
                            try:
                                res = client.toggle_user_active(u["id"])
                                st.success(res.get("message", "User unblocked."))
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error: {e}")
                    
                    # 2. Toggle Admin Privilege
                    admin_btn_label = "Demote to User" if u.get("is_admin") else "Promote to Admin"
                    if st.button(f"👑 {admin_btn_label}", key=f"adm_{u['id']}", use_container_width=True):
                        try:
                            res = client.toggle_user_admin(u["id"])
                            st.info(res.get("message", "Role updated."))
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")
                    
                    # 3. Permanent Deletion with safety confirm
                    with st.popover(f"🗑️ {t('admin_delete_btn')}", use_container_width=True):
                        st.error(f"⚠️ Are you sure you want to permanently delete **{u['email']}**?")
                        st.write("All their channel sets, monitored channels, and metrics will be wiped out.")
                        if st.button("Confirm Delete", key=f"del_confirm_{u['id']}", type="primary"):
                            try:
                                res = client.delete_user(u["id"])
                                st.success(res.get("message", "User deleted."))
                                st.rerun()
                            except Exception as e:
                                st.error(f"Deletion failed: {e}")
