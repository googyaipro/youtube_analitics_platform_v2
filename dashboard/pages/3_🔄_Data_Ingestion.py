import streamlit as st
from utils.api_client import APIClient

st.set_page_config(page_title="Data Ingestion", page_icon="🔄", layout="wide")
st.title("🔄 Ingest Channel Data into BigQuery & GCS")

client = APIClient()

st.markdown("""
Trigger an automated ETL pipeline run:
1. **Extract**: Fetch channel details and video metrics via **YouTube Data API v3**.
2. **Raw Archive**: Store immutable JSON payload into **Google Cloud Storage (GCS)**.
3. **Load**: Upsert normalized rows into **BigQuery** analytical tables.
""")

with st.form("ingest_form"):
    channel_input = st.text_input(
        "YouTube Channel Handle or Channel ID",
        value="@GoogleCloud",
        help="Provide a handle (e.g. @GoogleCloud) or Channel ID (e.g. UC_x5XG1OV2P6uZZ5FSM9Ttw)"
    )
    max_videos = st.slider("Max Recent Videos to Sync", min_value=5, max_value=50, value=20)
    submitted = st.form_submit_button("🚀 Start Ingestion Pipeline")

if submitted:
    if not channel_input.strip():
        st.error("Please provide a valid channel handle or ID.")
    else:
        with st.spinner(f"Ingesting data for {channel_input}..."):
            result = client.trigger_sync(channel_identifier=channel_input.strip(), max_videos=max_videos)
            
            if result.get("status") == "SUCCESS":
                st.success(f"Successfully ingested data for channel: **{result.get('channel_title')}**!")
                
                col1, col2 = st.columns(2)
                col1.info(f"📹 **Videos Synced**: {result.get('videos_synced')}")
                col2.info(f"📦 **Raw Backup Path**: `{result.get('raw_storage_uri')}`")
            else:
                st.error(f"Ingestion failed: {result.get('message', 'Unknown error')}")
