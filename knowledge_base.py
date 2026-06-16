import json

import streamlit as st

from project_paths import KB_METADATA_PATH


@st.cache_data
def load_kb():
    with open(KB_METADATA_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle)


@st.cache_data
def build_context(data):
    lines = []
    for item in data:
        cid = item.get("control_id", "")
        title = item.get("title", "")
        desc = item.get("description", "")[:150]
        lines.append(f"[{cid}] {title}: {desc}...")
    return "\n".join(lines)
