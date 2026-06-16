# Chief of Staff Agent

## Aurivian / Festizio — Personal Thought Partner

> "I don't want to stop thinking or working. Supercharging me means I'm
> tireless. I don't take breaks. I'm always thinking, always working, always on."

---

## Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set your Anthropic API key
export ANTHROPIC_API_KEY=sk-ant-...

# 3. Run it
python chief_of_staff.py
```

---

## Usage

| Command | When to use |
|---|---|
| `python chief_of_staff.py` | Returning from a break — get the status brief |
| `python chief_of_staff.py --debrief` | Quick update, no conversation |
| `python chief_of_staff.py --thread "Zee build"` | Jump to a specific thread |
| `python chief_of_staff.py --research "topic"` | Immediate research |
| `python chief_of_staff.py "your thought"` | Start with something specific |

---

## In-session commands

| Type | What happens |
|---|---|
| `/research <topic>` | Triggers live web search |
| `/debrief` | Status brief across all threads |
| `/threads` | List all active threads |
| `/note <thing>` | Save something to open questions |
| `/memory` | Dump raw memory state |
| `exit` or `done` | End session gracefully |

---

## How context works

The agent's full context lives in `CLAUDE.md`. Edit it to:

- Update active threads as they evolve
- Add new customers, products, or priorities
- Note new artifacts or deliverables

`memory.json` stores session state automatically — findings, open questions, notes. It persists between runs.

---

## The agent team (what comes next)

```
Chief of Staff (this agent)
├── Research Agent     — continuous external signal monitoring
├── Brief Agent        — generates the daily Pulse brief
├── KOL Agent          — builds and maintains KOL profiles
└── Congress Agent     — pre/live/post congress intelligence
```
