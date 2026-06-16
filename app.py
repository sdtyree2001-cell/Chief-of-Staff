"""
Chief of Staff — Streamlit UI
Aurivian / Festizio
"""

import streamlit as st
import anthropic
import json
from datetime import datetime
from pathlib import Path

from chief_of_staff import (
    load_claude_md,
    load_memory,
    save_memory,
    build_system_prompt,
    append_log,
    summarize_session,
)

# ── PAGE CONFIG ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Aurivian — Chief of Staff",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── STYLES ────────────────────────────────────────────────────────────────────

st.markdown("""
<style>
  /* Dark, clean, minimal */
  .stApp { background-color: #0f0f0f; }

  [data-testid="stSidebar"] {
    background-color: #141414;
    border-right: 1px solid #222;
  }

  /* Hide default Streamlit header/footer */
  #MainMenu, header, footer { visibility: hidden; }

  /* Chat bubbles */
  [data-testid="stChatMessage"] {
    background-color: #1a1a1a;
    border: 1px solid #222;
    border-radius: 8px;
    padding: 4px 8px;
    margin-bottom: 8px;
  }

  /* Chat input */
  [data-testid="stChatInputTextArea"] {
    background-color: #1a1a1a !important;
    border: 1px solid #333 !important;
    color: #e0e0e0 !important;
  }

  /* Sidebar buttons */
  .stButton > button {
    background-color: #1e1e1e;
    border: 1px solid #2a2a2a;
    color: #ccc;
    border-radius: 6px;
    width: 100%;
    text-align: left;
    font-size: 13px;
    padding: 6px 12px;
    margin-bottom: 2px;
    transition: background 0.15s;
  }
  .stButton > button:hover {
    background-color: #2a2a2a;
    border-color: #444;
    color: #fff;
  }

  /* Title area */
  .cos-header {
    font-size: 11px;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: #555;
    margin-bottom: 2px;
  }
  .cos-title {
    font-size: 20px;
    font-weight: 700;
    color: #e0e0e0;
    margin-bottom: 4px;
  }
  .cos-subtitle {
    font-size: 12px;
    color: #444;
  }

  /* Searching indicator */
  .search-indicator {
    font-size: 12px;
    color: #555;
    font-style: italic;
    padding: 4px 0;
  }
</style>
""", unsafe_allow_html=True)

# ── SESSION STATE INIT ────────────────────────────────────────────────────────

if "messages" not in st.session_state:
    st.session_state.messages = []

if "memory" not in st.session_state:
    st.session_state.memory = load_memory()
    st.session_state.memory["session_count"] = st.session_state.memory.get("session_count", 0) + 1
    st.session_state.memory["last_session"] = datetime.now().isoformat()
    save_memory(st.session_state.memory)

if "initialized" not in st.session_state:
    st.session_state.initialized = False

if "pending_input" not in st.session_state:
    st.session_state.pending_input = None

# ── SIDEBAR ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("""
    <div class="cos-header">Aurivian</div>
    <div class="cos-title">◆ Chief of Staff</div>
    <div class="cos-subtitle">Agent #1 · Always On</div>
    """, unsafe_allow_html=True)

    st.divider()

    memory = st.session_state.memory
    last = memory.get("last_session")
    if last:
        try:
            dt = datetime.fromisoformat(last)
            st.caption(f"Session #{memory.get('session_count', 1)}  ·  {dt.strftime('%b %d  %H:%M')}")
        except Exception:
            pass

    st.markdown("**Quick actions**")

    if st.button("◎  Status brief", key="btn_debrief"):
        st.session_state.pending_input = (
            "Give me your status brief. What have you been working on "
            "while I was away? What did you find? What do you recommend?"
        )

    if st.button("⊞  All threads", key="btn_threads"):
        st.session_state.pending_input = "List all active threads and where we stand on each one."

    if st.button("↺  New session", key="btn_new"):
        # Summarize before clearing
        history = [
            {"role": m["role"], "content": m["content"]}
            for m in st.session_state.get("messages", [])
            if m["role"] in ("user", "assistant")
        ]
        if history:
            client = anthropic.Anthropic()
            summarize_session(client, history, st.session_state.memory)
        st.session_state.messages = []
        st.session_state.initialized = False
        st.session_state.pending_input = None
        st.rerun()

    st.divider()
    st.markdown("**Active threads**")

    threads = [
        ("1", "Zee's build spec"),
        ("2", "argenx / Vyvgart"),
        ("3", "UCB / Bimzelx"),
        ("4", "Product vision"),
        ("5", "Agent team"),
    ]
    for num, name in threads:
        if st.button(f"{num}  {name}", key=f"thread_{num}"):
            st.session_state.pending_input = (
                f"Let's work on thread {num}: '{name}'. "
                f"What's the current state and what's the next move?"
            )

    st.divider()

    with st.expander("Memory state", expanded=False):
        last_summary = memory.get("last_session_summary", "")
        if last_summary:
            st.markdown("**Last session**")
            st.caption(last_summary)

        action_items = memory.get("last_action_items", [])
        if action_items:
            st.markdown("**Action items**")
            for a in action_items:
                st.caption(f"· {a}")

        findings = memory.get("findings", [])
        if findings:
            st.markdown("**Recent findings**")
            for f in findings[-3:]:
                st.caption(f)

        questions = memory.get("open_questions", [])
        if questions:
            st.markdown("**Open questions**")
            for q in questions:
                st.caption(f"· {q}")

        if not last_summary and not action_items and not findings and not questions:
            st.caption("No notes yet.")

# ── MAIN CHAT AREA ────────────────────────────────────────────────────────────

st.markdown("""
<div style="padding: 16px 0 8px 0;">
  <span style="font-size:18px; font-weight:700; color:#e0e0e0;">Chief of Staff</span>
  <span style="font-size:12px; color:#444; margin-left:12px;">Aurivian · Festizio</span>
</div>
""", unsafe_allow_html=True)

# Render existing messages
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ── RESPONSE ENGINE ───────────────────────────────────────────────────────────

def get_response(user_text: str):
    context = load_claude_md()
    memory  = st.session_state.memory
    system  = build_system_prompt(context, memory)

    # Build API message history (exclude system)
    api_messages = [
        {"role": m["role"], "content": m["content"]}
        for m in st.session_state.messages
        if m["role"] in ("user", "assistant")
    ]

    client = anthropic.Anthropic()

    with st.chat_message("assistant"):
        placeholder   = st.empty()
        full_response = ""

        def stream_to_placeholder(msgs):
            nonlocal full_response
            text_buf = ""
            tool_block = None

            with client.messages.stream(
                model="claude-opus-4-5",
                max_tokens=4096,
                system=system,
                messages=msgs,
                tools=[{"type": "web_search_20250305", "name": "web_search"}],
            ) as stream:
                for event in stream:
                    if hasattr(event, "type"):
                        if event.type == "content_block_delta" and hasattr(event.delta, "text"):
                            text_buf    += event.delta.text
                            full_response += event.delta.text
                            placeholder.markdown(full_response + "▌")
                        elif event.type == "content_block_start":
                            cb = getattr(event, "content_block", None)
                            if cb and getattr(cb, "type", None) == "tool_use":
                                tool_block = cb

                final = stream.get_final_message()

            return final, tool_block

        final, tool_block = stream_to_placeholder(api_messages)

        # Handle tool use (web search)
        if final.stop_reason == "tool_use":
            for block in final.content:
                if hasattr(block, "type") and block.type == "tool_use":
                    query = block.input.get("query", "")
                    placeholder.markdown(
                        full_response
                        + f"\n\n*Searching: {query}...*"
                    )

                    # Append tool use + result to messages
                    api_messages.append({
                        "role": "assistant",
                        "content": final.content,
                    })
                    api_messages.append({
                        "role": "user",
                        "content": [{
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": (
                                "Web search executed. Synthesize findings from your "
                                "knowledge and the search context to answer fully."
                            ),
                        }],
                    })

                    # Continue streaming after tool result
                    final2, _ = stream_to_placeholder(api_messages)

        placeholder.markdown(full_response)

    # Persist
    st.session_state.messages.append({"role": "assistant", "content": full_response})

    append_log(
        f"**Session #{memory['session_count']}**\n\n"
        f"**YOU:** {user_text}\n\n"
        f"**CHIEF OF STAFF:** {full_response}"
    )

    lower = full_response.lower()
    if any(w in lower for w in ["found", "discovered", "research shows", "according to"]):
        snippet = full_response.split("\n\n")[0][:250]
        memory.setdefault("findings", []).append(
            f"[{datetime.now().strftime('%m/%d %H:%M')}] {snippet}"
        )
        memory["findings"] = memory["findings"][-20:]
        save_memory(memory)
        st.session_state.memory = memory

# ── AUTO-OPEN WITH STATUS BRIEF ───────────────────────────────────────────────

if not st.session_state.initialized and not st.session_state.messages:
    st.session_state.initialized = True
    opening = (
        "i'm back. what have you been working on while i was gone? "
        "give me the status brief and let's figure out what to do next."
    )
    st.session_state.messages.append({"role": "user", "content": opening})
    with st.chat_message("user"):
        st.markdown(opening)
    get_response(opening)

# ── SIDEBAR BUTTON INJECTION ──────────────────────────────────────────────────

if st.session_state.pending_input:
    text = st.session_state.pending_input
    st.session_state.pending_input = None
    st.session_state.messages.append({"role": "user", "content": text})
    with st.chat_message("user"):
        st.markdown(text)
    get_response(text)

# ── CHAT INPUT ────────────────────────────────────────────────────────────────

if prompt := st.chat_input("Message your Chief of Staff..."):
    # Handle slash commands
    if prompt.lower().startswith("/research "):
        prompt = f"Research this right now and tell me what you find: {prompt[10:].strip()}"
    elif prompt.lower() == "/debrief":
        prompt = "Give me a quick status brief across all active threads."
    elif prompt.lower() == "/threads":
        prompt = "List all active threads and where we stand on each one."
    elif prompt.lower().startswith("/note "):
        note = prompt[6:].strip()
        st.session_state.memory.setdefault("open_questions", []).append(note)
        save_memory(st.session_state.memory)
        with st.chat_message("assistant"):
            st.markdown(f"Noted: *{note}*")
        st.session_state.messages.append({"role": "assistant", "content": f"Noted: *{note}*"})
        st.rerun()

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    get_response(prompt)
