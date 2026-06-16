#!/usr/bin/env python3
"""
Chief of Staff UI — Aurivian
=============================
A clean, refined interface for conversing with your Chief of Staff agent.
Light theme, sticky notes, briefs, action items, and real-time chat.
"""

import streamlit as st
import json
import os
import anthropic
from datetime import datetime
from pathlib import Path
from typing import Optional

# ── PAGE CONFIG ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Chief of Staff — Aurivian",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Light theme CSS (Jony Ive aesthetic)
st.markdown("""
<style>
    body {
        background-color: #ffffff;
        color: #333333;
    }
    .stApp {
        background-color: #ffffff;
    }
    .main {
        background-color: #ffffff;
    }
    .stTabs [data-baseweb="tab-list"] {
        background-color: #f8f9fa;
        border-bottom: 1px solid #e0e0e0;
    }
    .stTabs [aria-selected="true"] {
        border-bottom-color: #000000;
    }
    h1, h2, h3 {
        color: #1a1a1a;
        font-weight: 600;
    }
    .brief-box {
        background-color: #f8f9fa;
        padding: 20px;
        border-radius: 8px;
        border-left: 4px solid #000000;
        margin: 12px 0;
    }
    .action-item {
        background-color: #f0f0f0;
        padding: 12px;
        border-radius: 6px;
        margin: 8px 0;
        border-left: 3px solid #888888;
    }
    .action-item.done {
        background-color: #e8f5e9;
        border-left-color: #4caf50;
    }
    .sticky-note {
        background-color: #fffacd;
        padding: 12px;
        border-radius: 4px;
        margin: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        border: 1px solid #f0e68c;
    }
    .status-badge {
        display: inline-block;
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 12px;
        font-weight: 600;
    }
    .status-pending { background-color: #fff3cd; color: #856404; }
    .status-in_progress { background-color: #cfe2ff; color: #084298; }
    .status-done { background-color: #d1e7dd; color: #0f5132; }
    .status-blocked { background-color: #f8d7da; color: #842029; }
</style>
""", unsafe_allow_html=True)

# ── PATHS ────────────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent
ACTION_ITEMS_FILE = BASE_DIR / "action_items.json"
AURIVIAN_STATE_FILE = BASE_DIR / "aurivian_state.md"
COMPETITIVE_FILE = BASE_DIR / "competitive_landscape.md"
FUNDING_FILE = BASE_DIR / "funding_tracker.md"
DEBRIEF_FILE = BASE_DIR / "debrief_log.md"
STICKY_NOTES_FILE = BASE_DIR / "sticky_notes.json"

# ── SESSION STATE ────────────────────────────────────────────────────────────

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "sticky_notes" not in st.session_state:
    # Load sticky notes from file
    if STICKY_NOTES_FILE.exists():
        with open(STICKY_NOTES_FILE) as f:
            st.session_state.sticky_notes = json.load(f).get("notes", [])
    else:
        st.session_state.sticky_notes = []

# ── UTILITIES ────────────────────────────────────────────────────────────────

def load_json(path: Path) -> dict:
    """Load JSON file safely."""
    if path.exists():
        try:
            with open(path) as f:
                return json.load(f)
        except:
            return {}
    return {}

def load_markdown(path: Path) -> str:
    """Load markdown file safely."""
    if path.exists():
        return path.read_text()
    return "No data available"

def save_sticky_notes():
    """Save sticky notes to file."""
    with open(STICKY_NOTES_FILE, "w") as f:
        json.dump({"notes": st.session_state.sticky_notes}, f, indent=2)

def get_latest_brief() -> Optional[str]:
    """Extract the latest brief from debrief_log.md."""
    if not DEBRIEF_FILE.exists():
        return None
    
    content = DEBRIEF_FILE.read_text()
    briefs = content.split("## Cycle:")
    
    if len(briefs) > 1:
        return "## Cycle:" + briefs[-1].strip()
    return None

def get_status_badge(status: str) -> str:
    """Return HTML badge for status."""
    status_class = f"status-{status}"
    return f'<span class="status-badge {status_class}">{status.upper()}</span>'

# ── HEADER ───────────────────────────────────────────────────────────────────

col1, col2 = st.columns([6, 1])
with col1:
    st.title("🤖 Chief of Staff")
    st.markdown("*Your thought partner for Aurivian*")

with col2:
    st.caption(f"Last update: {datetime.now().strftime('%H:%M')}")

st.divider()

# ── TABS ─────────────────────────────────────────────────────────────────────

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "💬 Conversation", 
    "📋 Latest Brief", 
    "✅ Action Items", 
    "📌 Sticky Notes", 
    "📊 Context"
])

# ── TAB 1: CONVERSATION ──────────────────────────────────────────────────────

with tab1:
    st.subheader("Chat with Chief of Staff")
    st.markdown("Ask questions, brainstorm ideas, or get updates on specific topics.")
    
    # Chat history
    for i, msg in enumerate(st.session_state.chat_history):
        if msg["role"] == "user":
            with st.chat_message("user"):
                st.write(msg["content"])
        else:
            with st.chat_message("assistant"):
                st.write(msg["content"])
    
    # Input
    user_input = st.chat_input("What's on your mind?")
    
    if user_input:
        # Add user message to history
        st.session_state.chat_history.append({
            "role": "user",
            "content": user_input
        })
        
        # Load context
        context = {
            "action_items": load_json(ACTION_ITEMS_FILE),
            "aurivian_state": load_markdown(AURIVIAN_STATE_FILE),
            "competitive_landscape": load_markdown(COMPETITIVE_FILE),
            "funding": load_markdown(FUNDING_FILE),
        }
        
        # Build system prompt with context
        system_prompt = f"""You are the Chief of Staff for Aurivian — a sharp, pragmatic thought partner.

You have access to current company state:
- Action items and priorities
- Competitive landscape
- Funding opportunities
- Company strategy and vision

Be direct, specific, and actionable. Match the founder's energy. Use real numbers and file paths.

Current Context:
{json.dumps(context, indent=2)}"""
        
        # Call Claude
        with st.spinner("Thinking..."):
            try:
                client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
                response = client.messages.create(
                    model="claude-opus-4-5",
                    max_tokens=1000,
                    system=system_prompt,
                    messages=[{"role": m["role"], "content": m["content"]} for m in st.session_state.chat_history]
                )
                
                assistant_message = response.content[0].text
                st.session_state.chat_history.append({
                    "role": "assistant",
                    "content": assistant_message
                })
                
                st.rerun()
            except Exception as e:
                st.error(f"Error: {str(e)}")

# ── TAB 2: LATEST BRIEF ──────────────────────────────────────────────────────

with tab2:
    st.subheader("Latest Chief of Staff Brief")
    
    brief = get_latest_brief()
    if brief:
        st.markdown(f"""<div class="brief-box">{brief}</div>""", unsafe_allow_html=True)
    else:
        st.info("No briefs yet. The Chief of Staff will generate briefs every 2 hours.")

# ── TAB 3: ACTION ITEMS ──────────────────────────────────────────────────────

with tab3:
    st.subheader("Action Items")
    
    action_items = load_json(ACTION_ITEMS_FILE)
    
    if action_items and "work_streams" in action_items:
        for stream_key, stream in action_items["work_streams"].items():
            st.markdown(f"### {stream.get('name', stream_key)}")
            st.markdown(stream.get('purpose', ''))
            
            for item in stream.get("items", []):
                cols = st.columns([1, 3, 1, 1])
                
                with cols[0]:
                    status = item.get("status", "pending")
                    st.markdown(get_status_badge(status), unsafe_allow_html=True)
                
                with cols[1]:
                    st.markdown(f"**{item['title']}**")
                    st.caption(item.get("description", ""))
                
                with cols[2]:
                    priority = item.get("priority", "medium")
                    st.caption(f"📌 {priority}")
                
                with cols[3]:
                    due = item.get("due", "TBD")
                    st.caption(f"📅 {due}")
    else:
        st.info("No action items loaded yet.")

# ── TAB 4: STICKY NOTES ──────────────────────────────────────────────────────

with tab4:
    st.subheader("Sticky Notes — Ideas & Brainstorms")
    st.markdown("Post ideas here as you brainstorm with the Chief of Staff.")
    
    # Add new note
    cols = st.columns([4, 1])
    with cols[0]:
        new_note = st.text_input("New idea:", placeholder="Type an idea or thought...")
    with cols[1]:
        if st.button("➕ Add", key="add_note"):
            if new_note:
                st.session_state.sticky_notes.append({
                    "id": len(st.session_state.sticky_notes),
                    "text": new_note,
                    "created_at": datetime.now().isoformat()
                })
                save_sticky_notes()
                st.rerun()
    
    # Display notes in a grid
    if st.session_state.sticky_notes:
        cols = st.columns(3)
        for i, note in enumerate(st.session_state.sticky_notes):
            with cols[i % 3]:
                st.markdown(f"""<div class="sticky-note">{note['text']}</div>""", unsafe_allow_html=True)
                if st.button("🗑️ Delete", key=f"delete_{note['id']}", use_container_width=True):
                    st.session_state.sticky_notes.pop(i)
                    save_sticky_notes()
                    st.rerun()
    else:
        st.markdown("*No notes yet. Add your first idea!*")

# ── TAB 5: CONTEXT ───────────────────────────────────────────────────────────

with tab5:
    st.subheader("Company Context")
    
    subcols = st.columns(2)
    
    with subcols[0]:
        with st.expander("📍 Aurivian State", expanded=True):
            st.markdown(load_markdown(AURIVIAN_STATE_FILE))
    
    with subcols[1]:
        with st.expander("🎯 Competitive Landscape"):
            st.markdown(load_markdown(COMPETITIVE_FILE))
    
    with subcols[0]:
        with st.expander("💰 Funding Opportunities"):
            st.markdown(load_markdown(FUNDING_FILE))
    
    with subcols[1]:
        with st.expander("📂 Raw JSON (Action Items)"):
            st.json(load_json(ACTION_ITEMS_FILE))

# ── FOOTER ───────────────────────────────────────────────────────────────────

st.divider()
st.markdown("""
---
**Chief of Staff Agent** • Runs every 2 hours • Updates auto-commit to GitHub  
[View on GitHub](https://github.com/sdtyree2001-cell/Chief-of-Staff) | Last cycle: Check debrief_log.md
""")
