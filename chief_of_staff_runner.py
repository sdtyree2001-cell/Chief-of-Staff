#!/usr/bin/env python3
"""
Chief of Staff Runner — Entry Point for GitHub Actions
=======================================================
This script runs the Chief of Staff agent every 2 hours.
It processes action items, works on priorities, and updates tracking files.

Usage:
    python chief_of_staff_runner.py
"""

import anthropic
import json
import os
from datetime import datetime
from pathlib import Path

# ── PATHS ────────────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent
ACTION_ITEMS_FILE = BASE_DIR / "action_items.json"
AURIVIAN_STATE_FILE = BASE_DIR / "aurivian_state.md"
COMPETITIVE_FILE = BASE_DIR / "competitive_landscape.md"
FUNDING_FILE = BASE_DIR / "funding_tracker.md"
DEBRIEF_FILE = BASE_DIR / "debrief_log.md"

# ── MAIN ─────────────────────────────────────────────────────────────────────

def load_tracking_files() -> dict:
    """Load all tracking files for the Chief of Staff context."""
    context = {}
    
    if ACTION_ITEMS_FILE.exists():
        with open(ACTION_ITEMS_FILE) as f:
            context["action_items"] = json.load(f)
    
    if AURIVIAN_STATE_FILE.exists():
        context["aurivian_state"] = AURIVIAN_STATE_FILE.read_text()
    
    if COMPETITIVE_FILE.exists():
        context["competitive_landscape"] = COMPETITIVE_FILE.read_text()
    
    if FUNDING_FILE.exists():
        context["funding_tracker"] = FUNDING_FILE.read_text()
    
    return context


def build_system_prompt() -> str:
    """Build the system prompt for the Chief of Staff agent."""
    return """You are the Chief of Staff for Aurivian — a focused, pragmatic work partner who continues the founder's momentum between sessions.

Your job:
- Continue work: Move action items forward while the founder is away
- Track outcomes: Log what you accomplished and what you learned
- Brief on return: Give sharp, specific updates when the founder returns
- Remember what matters: Keep only critical action items and decisions

Every 2-hour cycle, you will:
1. Review action items (pending tasks)
2. Research and make progress on high-priority items (Aurivian Oversight, Competitive Intelligence, Business Development, Funding)
3. Update tracking files with your findings
4. Generate a brief for when the founder returns

Communication style:
- Direct and specific — no vague summaries
- Assume the founder is fast-moving — match that pace
- Use real numbers, real names, real file paths
- End with clear recommendations

Remember: This is a 2-hour cycle. You won't solve everything, but move the needle on what matters most."""


def run_agent_cycle(context: dict) -> str:
    """Run one cycle of the Chief of Staff agent."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    client = anthropic.Anthropic(api_key=api_key)
    
    # Build the context message
    context_msg = f"""
# Current Aurivian Status (as of this cycle)

## Action Items
{json.dumps(context.get("action_items", {}), indent=2)}

## Aurivian State
{context.get("aurivian_state", "No state file found")}

## Competitive Landscape
{context.get("competitive_landscape", "No competitive landscape found")}

## Funding Opportunities
{context.get("funding_tracker", "No funding tracker found")}

---

## Your Task This Cycle

1. Identify the top 3 action items by priority (from action_items.json)
2. For each, research and make meaningful progress:
   - Aurivian Oversight: Any progress on alignment? Terumo/Argenx status?
   - Competitive Intelligence: Any new market moves? Threats?
   - Business Development: What are the top 3 BDR opportunities? What's blocking deals?
   - Funding: Any angel leads or grant opportunities?
3. Generate a STATUS BRIEF for the founder (use the template below)

## Brief Template (use this exact format)

# Chief of Staff — Status Brief

**Cycle:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}

## Aurivian Oversight
- [priority/action] → [status/progress]

## Competitive Intelligence
- [market move or threat] → [impact]

## Business Development
- [top opportunity] → [fit score, trigger, next action]

## Funding
- [funding lead] → [action]

## One thing I need your input on:
[Decision or question]

---

Start your cycle now. Work through priorities. Research what you can. Generate the brief when complete.
"""
    
    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=4000,
        system=build_system_prompt(),
        messages=[
            {
                "role": "user",
                "content": context_msg
            }
        ]
    )
    
    return response.content[0].text


def update_debrief_log(brief: str) -> None:
    """Append the brief to the debrief log."""
    timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
    
    # Read existing log if it exists
    if DEBRIEF_FILE.exists():
        existing = DEBRIEF_FILE.read_text()
    else:
        existing = "# Debrief Log — Chief of Staff\n\n"
    
    # Append new brief with timestamp
    new_entry = f"\n---\n\n## Cycle: {timestamp}\n\n{brief}\n"
    
    DEBRIEF_FILE.write_text(existing + new_entry)
    print(f"✓ Updated debrief log: {DEBRIEF_FILE}")


def main():
    """Main entry point."""
    print(f"🤖 Chief of Staff Agent — Starting cycle at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    
    # Load tracking context
    print("📂 Loading tracking files...")
    context = load_tracking_files()
    
    # Run the agent cycle
    print("🔄 Running Chief of Staff agent cycle...")
    brief = run_agent_cycle(context)
    
    # Update debrief log
    print("📝 Updating debrief log...")
    update_debrief_log(brief)
    
    # Print brief to stdout for workflow visibility
    print("\n" + "="*80)
    print("CHIEF OF STAFF BRIEF")
    print("="*80)
    print(brief)
    print("="*80)
    
    print("\n✅ Cycle complete. Tracking files ready for commit.")


if __name__ == "__main__":
    main()
