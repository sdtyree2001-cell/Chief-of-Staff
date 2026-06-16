#!/usr/bin/env python3
"""
Chief of Staff Agent — Aurivian / Festizio
==========================================
A tireless thought partner that continues working while the founder is away.

Usage:
    python chief_of_staff.py                     # Return from a break
    python chief_of_staff.py --debrief           # Quick status only
    python chief_of_staff.py --thread <name>     # Work a specific thread
    python chief_of_staff.py --research <topic>  # Research a topic now
    python chief_of_staff.py "your message"      # Start with a specific thought
"""

import anthropic
import json
import os
import sys
import argparse
import re
from datetime import datetime
from pathlib import Path

# ── CONFIG ──────────────────────────────────────────────────────────────────

MODEL       = "claude-opus-4-5"
MEMORY_FILE = Path(__file__).parent / "memory.json"
LOG_FILE    = Path(__file__).parent / "debrief_log.md"
CLAUDE_MD   = Path(__file__).parent / "CLAUDE.md"

# ── PERSISTENCE ─────────────────────────────────────────────────────────────

def load_claude_md() -> str:
    if CLAUDE_MD.exists():
        return CLAUDE_MD.read_text()
    return ""

def load_memory() -> dict:
    if MEMORY_FILE.exists():
        with open(MEMORY_FILE) as f:
            return json.load(f)
    return {
        "last_session": None,
        "session_count": 0,
        "findings": [],
        "open_questions": [],
        "thread_notes": {},
        "drafts_in_progress": [],
    }

def save_memory(memory: dict):
    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f, indent=2, default=str)

def append_log(content: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(LOG_FILE, "a") as f:
        f.write(f"\n\n---\n### {timestamp}\n{content}\n")

# ── SESSION SUMMARIZER ───────────────────────────────────────────────────────

SUMMARIZE_PROMPT = """\
You are reviewing a completed Chief of Staff session for Aurivian.

Extract the key information and return ONLY a valid JSON object — no prose, no markdown fences.

Required fields:
{
  "session_summary": "one sentence capturing what this session was about",
  "key_decisions": ["decision 1", "decision 2"],
  "action_items": ["specific next step 1", "specific next step 2"],
  "thread_updates": {"Thread Name": "brief note on what moved forward"}
}

Rules:
- key_decisions: max 5, specific and concrete
- action_items: max 5, owned and actionable (include who if clear)
- thread_updates: only threads that actually came up
- If nothing was decided or actioned, return empty arrays

Conversation to summarize:
"""

def summarize_session(client: anthropic.Anthropic, history: list, memory: dict):
    """Summarize the session and persist decisions + action items to memory."""
    text_turns = [m for m in history if isinstance(m.get("content"), str)]
    if len(text_turns) < 2:
        save_memory(memory)
        return

    conversation = "\n\n".join(
        f"{'FOUNDER' if m['role'] == 'user' else 'CHIEF OF STAFF'}: {m['content']}"
        for m in text_turns
    )

    print("\n  [Saving session summary...]\n", flush=True)
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            messages=[{
                "role":    "user",
                "content": SUMMARIZE_PROMPT + conversation[-6000:],
            }],
        )

        raw = response.content[0].text.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
        raw = re.sub(r"\s*```$",          "", raw, flags=re.MULTILINE)
        summary = json.loads(raw.strip())

        memory["last_session_summary"]  = summary.get("session_summary", "")
        memory["last_action_items"]     = summary.get("action_items", [])
        memory["last_key_decisions"]    = summary.get("key_decisions", [])

        for thread, note in summary.get("thread_updates", {}).items():
            memory.setdefault("thread_notes", {})[thread] = note

        memory.setdefault("session_history", []).append({
            "date":      datetime.now().strftime("%Y-%m-%d %H:%M"),
            "summary":   summary.get("session_summary", ""),
            "actions":   summary.get("action_items", []),
            "decisions": summary.get("key_decisions", []),
        })
        memory["session_history"] = memory["session_history"][-5:]

        n_actions = len(summary.get("action_items", []))
        print(f"  [Saved — {n_actions} action item(s) logged for next session]\n")

    except Exception as e:
        print(f"  [Summary save failed: {e} — saving base memory]\n")

    save_memory(memory)

# ── SYSTEM PROMPT ────────────────────────────────────────────────────────────

def build_system_prompt(context: str, memory: dict) -> str:
    last = memory.get("last_session", "First session")

    last_summary = memory.get("last_session_summary", "")
    last_actions = "\n".join(
        f"- {a}" for a in memory.get("last_action_items", [])
    ) or "None logged."
    last_decisions = "\n".join(
        f"- {d}" for d in memory.get("last_key_decisions", [])
    ) or "None logged."

    findings = "\n".join(
        f"- {f}" for f in memory.get("findings", [])[-5:]
    ) or "None yet."

    questions = "\n".join(
        f"- {q}" for q in memory.get("open_questions", [])
    ) or "None logged yet."

    thread_notes = memory.get("thread_notes", {})
    thread_summary = "\n".join(
        f"- **{k}:** {v}" for k, v in thread_notes.items()
    ) or "No thread notes yet."

    return f"""
{context}

---

## YOUR CURRENT STATE

**Last active:** {last}

**Sessions completed:** {memory.get('session_count', 0)}

**Last session summary:** {last_summary or "No prior session summary yet."}

**Action items from last session (follow up on these):**

{last_actions}

**Key decisions from last session:**

{last_decisions}

**Recent findings:**

{findings}

**Open questions you're tracking:**

{questions}

**Thread notes:**

{thread_summary}

---

## YOUR CAPABILITIES

You have access to the **web_search** tool. Use it proactively:

- When the founder asks about a topic, search before answering
- When working a thread autonomously, search to advance it
- When something in the news might affect the product or customers, flag it

Always cite sources. Format findings as:

[Finding] → [Source] → [Why it matters for Aurivian]

You can also:

- Draft documents, emails, prompts, or specs when asked
- Synthesize across multiple threads to find connections
- Recommend priorities when the founder is deciding what to work on next
- Push back when you think something is off — that's your job

---

## IMPORTANT: YOU ARE NOT A CHATBOT

You are a Chief of Staff. That means:

- **Initiative:** You don't just answer questions — you advance the work
- **Memory:** You hold all context above continuously across sessions
- **Judgment:** You prioritize, recommend, and push back when needed
- **Stamina:** The work continues even when the conversation ends

When the founder returns after being away, ALWAYS open with the status
brief format defined in the CLAUDE.md above.
"""

# ── TOOL HANDLING ────────────────────────────────────────────────────────────

def handle_tool_use(client, tool_use_block, history, system, memory):
    """Process a tool use request and return the updated response."""
    tool_name = tool_use_block.name
    tool_input = tool_use_block.input
    tool_use_id = tool_use_block.id

    print(f"\n  [Searching: {tool_input.get('query', '')}...]", flush=True)

    # Submit tool result back to the model
    history.append({
        "role": "assistant",
        "content": [tool_use_block]
    })

    history.append({
        "role": "user",
        "content": [{
            "type": "tool_result",
            "tool_use_id": tool_use_id,
            "content": "Web search executed. Please synthesize findings from your knowledge and the search context.",
        }]
    })

    return history

# ── SESSION ENGINE ───────────────────────────────────────────────────────────

def run_session(
    initial_message: str = None,
    debrief_only: bool = False,
    thread: str = None,
    research_topic: str = None,
):
    client  = anthropic.Anthropic()
    context = load_claude_md()
    memory  = load_memory()

    memory["session_count"] = memory.get("session_count", 0) + 1
    memory["last_session"]  = datetime.now().isoformat()
    save_memory(memory)

    system  = build_system_prompt(context, memory)
    history = []

    # Determine opening
    if debrief_only:
        opening = (
            "Give me your status brief. What have you been working on "
            "while I was away? What did you find? What do you recommend?"
        )
    elif thread:
        opening = (
            f"Let's work on the '{thread}' thread. What do you have so far "
            f"and what's the next move?"
        )
    elif research_topic:
        opening = f"Research this now and tell me what you find: {research_topic}"
    elif initial_message:
        opening = initial_message
    else:
        opening = (
            "i'm back. what have you been working on while i was gone? "
            "give me the status brief and let's figure out what to do next."
        )

    # Header
    print(f"\n{'═' * 64}")
    print(f"  AURIVIAN — CHIEF OF STAFF")
    print(f"  Session #{memory['session_count']}  ·  "
          f"{datetime.now().strftime('%A, %B %d %Y  %H:%M')}")
    print(f"{'═' * 64}\n")
    print(f"  YOU: {opening}\n")
    print(f"  CHIEF OF STAFF:\n")

    history.append({"role": "user", "content": opening})

    # ── Main loop ────────────────────────────────────────────────────────────

    while True:
        full_response = ""
        tool_use_block = None

        with client.messages.stream(
            model=MODEL,
            max_tokens=4096,
            system=system,
            messages=history,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
        ) as stream:
            for event in stream:
                if hasattr(event, "type"):
                    if event.type == "content_block_delta":
                        if hasattr(event.delta, "text"):
                            print(event.delta.text, end="", flush=True)
                            full_response += event.delta.text
                    elif event.type == "content_block_start":
                        if hasattr(event.content_block, "type"):
                            if event.content_block.type == "tool_use":
                                tool_use_block = event.content_block

            final_message = stream.get_final_message()

        # Handle tool use if present
        if final_message.stop_reason == "tool_use":
            for block in final_message.content:
                if hasattr(block, "type") and block.type == "tool_use":
                    history = handle_tool_use(client, block, history, system, memory)

            # Continue streaming after tool result
            print(f"\n  CHIEF OF STAFF (continued):\n")
            with client.messages.stream(
                model=MODEL,
                max_tokens=4096,
                system=system,
                messages=history,
                tools=[{"type": "web_search_20250305", "name": "web_search"}],
            ) as stream:
                for event in stream:
                    if hasattr(event, "type"):
                        if event.type == "content_block_delta":
                            if hasattr(event.delta, "text"):
                                print(event.delta.text, end="", flush=True)
                                full_response += event.delta.text

        print("\n")

        # Save to history and log
        history.append({"role": "assistant", "content": full_response})
        append_log(
            f"**Session #{memory['session_count']}**\n\n"
            f"**YOU:** {opening}\n\n"
            f"**CHIEF OF STAFF:** {full_response}"
        )

        # Extract and store findings (simple heuristic)
        lower = full_response.lower()
        if any(w in lower for w in ["found", "discovered", "research shows", "according to"]):
            snippet = full_response.split("\n\n")[0][:250]
            memory.setdefault("findings", []).append(
                f"[{datetime.now().strftime('%m/%d %H:%M')}] {snippet}"
            )
            memory["findings"] = memory["findings"][-20:]
            save_memory(memory)

        # Single-shot modes
        if debrief_only or research_topic:
            summarize_session(client, history, memory)
            return

        # Wait for input
        print("─" * 64)
        try:
            user_input = input("  YOU: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n")
            summarize_session(client, history, memory)
            print("  [Signing off. Brief you when you're back.]\n")
            return

        if not user_input:
            continue

        if user_input.lower() in ["exit", "quit", "bye", "done", "stop", "q"]:
            summarize_session(client, history, memory)
            print("  Got it. Brief you when you're back.\n")
            return

        # Special commands
        if user_input.lower().startswith("/research "):
            topic = user_input[10:].strip()
            user_input = f"Research this right now and tell me what you find: {topic}"
        elif user_input.lower() == "/debrief":
            user_input = "Give me a quick status brief across all active threads."
        elif user_input.lower() == "/threads":
            user_input = "List all active threads and where we stand on each one."
        elif user_input.lower() == "/memory":
            print(f"\n  [Memory state]\n{json.dumps(memory, indent=2, default=str)}\n")
            continue
        elif user_input.lower().startswith("/note "):
            note = user_input[6:].strip()
            memory.setdefault("open_questions", []).append(note)
            save_memory(memory)
            print(f"  [Noted: '{note}']\n")
            continue

        print(f"\n  CHIEF OF STAFF:\n")
        history.append({"role": "user", "content": user_input})
        opening = user_input

# ── ENTRY POINT ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Chief of Staff Agent — Aurivian / Festizio",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python chief_of_staff.py                          # Return from a break
  python chief_of_staff.py --debrief                # Quick status only
  python chief_of_staff.py --thread "Zee build"     # Work a specific thread
  python chief_of_staff.py --research "IMAAVY CIDP" # Research a topic
  python chief_of_staff.py "let's work on pricing"  # Open with a thought
        """
    )

    parser.add_argument("--debrief",  action="store_true",
                        help="Get a status brief only (no conversation)")
    parser.add_argument("--thread",   type=str,
                        help="Jump directly to working a specific thread")
    parser.add_argument("--research", type=str,
                        help="Research a specific topic immediately")
    parser.add_argument("message",    nargs="?",
                        help="Opening message to start the session with")

    args = parser.parse_args()

    run_session(
        initial_message = args.message,
        debrief_only    = args.debrief,
        thread          = args.thread,
        research_topic  = args.research,
    )

if __name__ == "__main__":
    main()
