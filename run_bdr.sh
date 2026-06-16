#!/bin/bash
# BDR Agent — daily cron wrapper
# Runs every morning at 8:00am Eastern

export ANTHROPIC_API_KEY="$(cat /Users/styree/.anthropic_key 2>/dev/null)"

if [ -z "$ANTHROPIC_API_KEY" ]; then
  echo "$(date): ERROR — ANTHROPIC_API_KEY not found in ~/.anthropic_key" \
    >> /Users/styree/Documents/Projects/Chief\ of\ Staff/outputs/cron.log
  exit 1
fi

/Library/Frameworks/Python.framework/Versions/3.14/bin/python3 \
  /Users/styree/Documents/Projects/Chief\ of\ Staff/bdr_agent.py \
  >> /Users/styree/Documents/Projects/Chief\ of\ Staff/outputs/cron.log 2>&1
