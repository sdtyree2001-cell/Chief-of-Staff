#!/usr/bin/env python3
"""
BDR Prospect Surveillance Agent — Aurivian / Festizio
=====================================================
Weekly surveillance of pharma/biotech trigger events.
Identifies companies approaching moments where they need Medical Affairs intelligence.

Run schedule: Every Sunday
Output: outputs/prospects/prospects_YYYY-MM-DD.csv

Usage:
    python bdr_agent.py              # Full run
    python bdr_agent.py --dry-run    # Test without writing output
    python bdr_agent.py --limit 10   # Limit raw events (for testing)
    python bdr_agent.py --lookback 30  # Only look back 30 days
"""

import anthropic
import requests
import csv
import json
import argparse
import feedparser
import re
import logging
import time
from datetime import datetime, timedelta, date
from pathlib import Path

# ── PATHS ─────────────────────────────────────────────────────────────────────

BASE_DIR   = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "outputs" / "prospects"
LOG_DIR    = BASE_DIR / "outputs"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

# ── LOGGING ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "bdr_agent.log"),
        logging.StreamHandler(),
    ]
)
log = logging.getLogger(__name__)

# ── CONFIG ────────────────────────────────────────────────────────────────────

MODEL    = "claude-opus-4-5"
LOOKBACK = 60  # default days to look back

RSS_FEEDS = {
    "Fierce Pharma":  "https://www.fiercepharma.com/rss/xml",
    "Endpoints News": "https://endpts.com/feed/",
    "BioPharma Dive": "https://www.biopharmadive.com/feeds/news/",
}

TRIGGER_KEYWORDS = [
    "PDUFA", "BLA submission", "NDA submission", "FDA approval", "FDA approved",
    "phase 3 results", "phase III results", "pivotal trial", "positive readout",
    "positive results", "indication expansion", "sNDA", "sBLA",
    "commercial launch", "market launch", "pre-launch",
    "head of medical affairs", "chief medical officer",
    "breakthrough designation", "priority review",
    "real-world evidence", "MSL", "medical science liaison",
]

CSV_COLUMNS = [
    "company_name", "ticker", "hq_location", "company_size",
    "product_name", "indication", "modality",
    "trigger_event", "trigger_date", "event_source",
    "stage", "pdufa_date", "competitors",
    "fit_score", "fit_rationale", "date_added",
]

FIT_ORDER = {"High": 0, "Medium": 1, "Low": 2}

# ── SOURCE 1: FDA (OpenFDA) ───────────────────────────────────────────────────

def fetch_fda_actions(lookback_days: int) -> list[dict]:
    """Fetch recent BLA/NDA submissions and approvals from OpenFDA."""
    end_dt   = date.today()
    start_dt = end_dt - timedelta(days=lookback_days)

    url = (
        "https://api.fda.gov/drug/drugsfda.json"
        f"?search=submissions.submission_status_date:[{start_dt}+TO+{end_dt}]"
        "&limit=100"
    )

    results = []
    try:
        resp = requests.get(url, timeout=20)
        if resp.status_code != 200:
            log.warning(f"OpenFDA: HTTP {resp.status_code}")
            return results

        data = resp.json()
        for item in data.get("results", []):
            sponsor  = item.get("sponsor_name", "Unknown")
            products = item.get("products", [{}])
            brand    = products[0].get("brand_name", "") if products else ""
            generic  = products[0].get("generic_name", "") if products else ""
            prod_name = brand or generic or "Unknown"

            for sub in item.get("submissions", []):
                status_date = sub.get("submission_status_date", "")
                sub_type    = sub.get("submission_type", "")
                sub_status  = sub.get("submission_status", "")

                if not status_date:
                    continue
                try:
                    sub_dt = datetime.strptime(status_date, "%Y%m%d")
                    if (date.today() - sub_dt.date()).days > lookback_days:
                        continue
                except ValueError:
                    continue

                trigger = None
                if sub_type in ("BLA", "NDA") and sub_status == "AP":
                    trigger = f"FDA Approval — {sub_type}"
                elif sub_type in ("BLA", "NDA") and sub_status in ("SB", "Filed"):
                    trigger = f"{sub_type} Submitted"
                elif sub_type == "SUPPL" and sub_status == "AP":
                    trigger = "Indication Expansion Approved"

                if trigger:
                    results.append({
                        "company_name":  sponsor,
                        "product_name":  prod_name,
                        "trigger_event": trigger,
                        "trigger_date":  sub_dt.strftime("%Y-%m-%d"),
                        "event_source":  "OpenFDA (api.fda.gov)",
                        "raw_source":    "FDA",
                        "headline":      f"{trigger}: {prod_name} ({sponsor})",
                        "summary":       f"{sub_type} {sub_status} for {prod_name} by {sponsor}",
                    })

        log.info(f"FDA: {len(results)} trigger events")
    except Exception as e:
        log.error(f"FDA fetch failed: {e}")

    return results


# ── SOURCE 2: CLINICALTRIALS.GOV ─────────────────────────────────────────────

def fetch_clinical_trials(lookback_days: int) -> list[dict]:
    """Fetch recent Phase 3 completions with results from ClinicalTrials.gov."""
    end_dt   = date.today()
    start_dt = end_dt - timedelta(days=lookback_days)

    params = {
        "query.term":           "phase 3",
        "filter.overallStatus": "COMPLETED",
        "pageSize":             50,
        "fields":               "protocolSection,hasResults",
        "filter.advanced":      f"AREA[LastUpdatePostDate]RANGE[{start_dt},{end_dt}]",
    }

    results = []
    try:
        resp = requests.get(
            "https://clinicaltrials.gov/api/v2/studies",
            params=params,
            timeout=20,
        )
        if resp.status_code != 200:
            log.warning(f"ClinicalTrials.gov: HTTP {resp.status_code}")
            return results

        data = resp.json()
        for study in data.get("studies", []):
            # Only studies that have posted results (positive readout likely)
            if not study.get("hasResults"):
                continue

            proto   = study.get("protocolSection", {})
            id_mod  = proto.get("identificationModule", {})
            status  = proto.get("statusModule", {})
            design  = proto.get("designModule", {})
            conds   = proto.get("conditionsModule", {})
            sponsor = proto.get("sponsorCollaboratorsModule", {})
            interv  = proto.get("interventionsModule", {})

            phases = design.get("phases", [])
            if "PHASE3" not in phases:
                continue

            company   = sponsor.get("leadSponsor", {}).get("name", "Unknown")
            nct_id    = id_mod.get("nctId", "")
            title     = id_mod.get("briefTitle", "")[:80]
            condition = ", ".join(conds.get("conditions", [])[:2])
            comp_date = status.get("completionDateStruct", {}).get("date", "")

            # Try to get drug name from interventions
            drug_name = ""
            for iv in interv.get("interventions", []):
                if iv.get("type") in ("DRUG", "BIOLOGICAL"):
                    drug_name = iv.get("name", "")
                    break

            results.append({
                "company_name":  company,
                "product_name":  drug_name or title,
                "indication":    condition,
                "trigger_event": "Phase 3 Completion with Results",
                "trigger_date":  comp_date or date.today().strftime("%Y-%m-%d"),
                "event_source":  f"ClinicalTrials.gov — {nct_id}",
                "raw_source":    "ClinicalTrials",
                "headline":      title,
                "summary":       f"Phase 3 completed with results: {title} ({condition})",
            })

        log.info(f"ClinicalTrials: {len(results)} completions with results")
    except Exception as e:
        log.error(f"ClinicalTrials fetch failed: {e}")

    return results


# ── SOURCE 3: NEWS RSS FEEDS ──────────────────────────────────────────────────

def fetch_news(lookback_days: int) -> list[dict]:
    """Pull recent articles from industry RSS feeds, filter by trigger keywords."""
    cutoff  = datetime.now() - timedelta(days=lookback_days)
    results = []

    for source, url in RSS_FEEDS.items():
        try:
            feed = feedparser.parse(
                url,
                agent="Mozilla/5.0 (compatible; AurivianBDR/1.0)",
            )
            count = 0
            for entry in feed.entries:
                published = entry.get("published_parsed") or entry.get("updated_parsed")
                if published:
                    pub_dt = datetime(*published[:6])
                    if pub_dt < cutoff:
                        continue

                title   = entry.get("title", "")
                summary = entry.get("summary", "")
                link    = entry.get("link", "")
                text    = f"{title} {summary}".lower()

                matched = [kw for kw in TRIGGER_KEYWORDS if kw.lower() in text]
                if not matched:
                    continue

                results.append({
                    "company_name":  "",
                    "product_name":  "",
                    "trigger_event": matched[0],
                    "trigger_date":  pub_dt.strftime("%Y-%m-%d") if published else "",
                    "event_source":  link,
                    "raw_source":    source,
                    "headline":      title,
                    "summary":       summary[:600],
                })
                count += 1

            log.info(f"{source}: {count} articles matched")
            time.sleep(0.5)
        except Exception as e:
            log.error(f"{source} feed failed: {e}")

    return results


# ── CLAUDE ENRICHMENT + SCORING ───────────────────────────────────────────────

ENRICH_PROMPT = """\
You are a business intelligence analyst for Aurivian — an AI-powered Medical Affairs intelligence company.

Aurivian's ideal prospect:
- Small or Mid pharma/biotech (<$10B market cap)
- Pre-launch (PDUFA in <6 months) OR early post-launch (<18 months)
- Specialty, rare disease, or complex indication (high Medical Affairs intensity)
- No known MA intelligence vendor (Sorcero, Within3, H1) in place

Scoring rules:
HIGH: Small/Mid company + specialty/rare indication + trigger <30 days + pre/early-launch
MEDIUM: Large company with underserved product team, OR 6-12mo pre-launch, OR moderate complexity
LOW: Large company with established MA, mature product >3yr, primary care, or known vendor

For each trigger event below, extract all available info and score it. Return a JSON array ONLY — no prose, no markdown fences.

Each object must have:
{{
  "company_name": "...",
  "ticker": "TICKER or empty string",
  "hq_location": "City, Country",
  "company_size": "Small|Mid|Large",
  "product_name": "...",
  "indication": "...",
  "modality": "small molecule|biologic|gene therapy|cell therapy|other",
  "trigger_event": "...",
  "trigger_date": "YYYY-MM-DD",
  "event_source": "...",
  "stage": "Pre-launch|Launched|Expanding",
  "pdufa_date": "YYYY-MM-DD or empty string",
  "competitors": "comma-separated list of key competitors",
  "fit_score": "High|Medium|Low",
  "fit_rationale": "1-2 sentences explaining the score"
}}

If data is unavailable, use an empty string. Do not omit fields. Flag incomplete records in fit_rationale.

Trigger events to process:
{events}
"""

def enrich_prospects(client: anthropic.Anthropic, raw: list[dict], batch_size: int = 8) -> list[dict]:
    """Use Claude to enrich and score each raw trigger event."""
    all_enriched = []

    for i in range(0, len(raw), batch_size):
        batch      = raw[i : i + batch_size]
        batch_num  = i // batch_size + 1
        events_str = json.dumps(batch, indent=2)

        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=4096,
                messages=[{
                    "role":    "user",
                    "content": ENRICH_PROMPT.format(events=events_str),
                }],
            )

            text = response.content[0].text.strip()

            # Strip markdown code fences if present
            text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.MULTILINE)
            text = re.sub(r'\s*```$', '', text, flags=re.MULTILINE)
            text = text.strip()

            # Try parsing the whole response as JSON first
            enriched = None
            try:
                parsed = json.loads(text)
                enriched = parsed if isinstance(parsed, list) else [parsed]
            except json.JSONDecodeError:
                # Fall back to extracting the first [...] block
                match = re.search(r'\[.*?\]', text, re.DOTALL)
                if match:
                    try:
                        enriched = json.loads(match.group())
                    except json.JSONDecodeError:
                        pass

            if enriched:
                all_enriched.extend(enriched)
                log.info(f"Batch {batch_num}: enriched {len(enriched)} prospects")
            else:
                log.warning(f"Batch {batch_num}: could not parse JSON — raw response snippet: {text[:200]}")

        except Exception as e:
            log.error(f"Batch {batch_num} enrichment failed: {e}")

        time.sleep(1)

    return all_enriched


# ── DEDUPLICATION ─────────────────────────────────────────────────────────────

def load_previous_prospects() -> set[str]:
    """Load company+product keys from the most recent CSV run."""
    existing  = set()
    csv_files = sorted(OUTPUT_DIR.glob("prospects_*.csv"), reverse=True)

    if not csv_files:
        return existing

    latest = csv_files[0]
    try:
        with open(latest, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                key = f"{row.get('company_name','').lower()}|{row.get('product_name','').lower()}"
                existing.add(key)
        log.info(f"Loaded {len(existing)} prior prospects from {latest.name}")
    except Exception as e:
        log.error(f"Could not load prior prospects: {e}")

    return existing


def deduplicate(prospects: list[dict], previous: set[str]) -> list[dict]:
    """Keep only prospects not seen in the previous run."""
    if not previous:
        return prospects

    out     = []
    skipped = 0
    for p in prospects:
        key = f"{p.get('company_name','').lower()}|{p.get('product_name','').lower()}"
        if key in previous:
            skipped += 1
        else:
            out.append(p)

    if skipped:
        log.info(f"Deduplication: dropped {skipped} repeat prospects")

    return out


# ── OUTPUT ────────────────────────────────────────────────────────────────────

def write_csv(prospects: list[dict], dry_run: bool = False) -> Path:
    today    = date.today().strftime("%Y-%m-%d")
    out_path = OUTPUT_DIR / f"prospects_{today}.csv"

    for p in prospects:
        p["date_added"] = today

    prospects.sort(key=lambda p: FIT_ORDER.get(p.get("fit_score", "Low"), 2))

    if dry_run:
        print(f"\n[DRY RUN] Would write {len(prospects)} prospects → {out_path}\n")
        for p in prospects[:8]:
            score = p.get("fit_score", "?")
            print(f"  [{score:6}]  {p.get('company_name','?')}  ·  {p.get('product_name','?')}")
            print(f"             {p.get('indication','?')}  ·  {p.get('stage','?')}")
            print(f"             {p.get('trigger_event','?')} ({p.get('trigger_date','?')})")
            print(f"             {p.get('fit_rationale','')}\n")
        return out_path

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(prospects)

    log.info(f"Wrote {len(prospects)} prospects → {out_path}")
    return out_path


# ── SUMMARY ───────────────────────────────────────────────────────────────────

def print_summary(prospects: list[dict], output_path: Path):
    w = 64
    print(f"\n{'═' * w}")
    print(f"  AURIVIAN — BDR PROSPECT SURVEILLANCE")
    print(f"  {date.today().strftime('%A, %B %d %Y')}")
    print(f"{'═' * w}\n")

    high   = [p for p in prospects if p.get("fit_score") == "High"]
    medium = [p for p in prospects if p.get("fit_score") == "Medium"]
    low    = [p for p in prospects if p.get("fit_score") == "Low"]

    print(f"  Total prospects : {len(prospects)}")
    print(f"  High fit        : {len(high)}")
    print(f"  Medium fit      : {len(medium)}")
    print(f"  Low fit         : {len(low)}")
    print(f"  Output          : {output_path.name}\n")

    if high:
        print(f"  ── HIGH FIT PROSPECTS ──\n")
        for p in high:
            print(f"  ◆  {p.get('company_name','?')} ({p.get('ticker','')})  ·  {p.get('product_name','?')}")
            print(f"     {p.get('indication','?')}  ·  {p.get('stage','?')}")
            print(f"     Trigger: {p.get('trigger_event','?')}  ({p.get('trigger_date','?')})")
            print(f"     {p.get('fit_rationale','')}\n")

    print(f"{'─' * w}\n")


# ── ENTRY POINT ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="BDR Prospect Surveillance Agent — Aurivian / Festizio"
    )
    parser.add_argument("--dry-run",  action="store_true",
                        help="Run without writing CSV output")
    parser.add_argument("--limit",    type=int, default=None,
                        help="Cap raw events before enrichment (for testing)")
    parser.add_argument("--lookback", type=int, default=LOOKBACK,
                        help=f"Days to look back (default: {LOOKBACK})")
    args = parser.parse_args()

    log.info(f"BDR Agent starting — lookback: {args.lookback} days")
    client = anthropic.Anthropic()

    # 1. Fetch from all sources
    log.info("Fetching FDA data...")
    fda_events = fetch_fda_actions(args.lookback)

    log.info("Fetching ClinicalTrials.gov data...")
    ct_events = fetch_clinical_trials(args.lookback)

    log.info("Fetching news feeds...")
    news_events = fetch_news(args.lookback)

    raw = fda_events + ct_events + news_events
    log.info(f"Total raw trigger events: {len(raw)}")

    if not raw:
        log.warning("No raw events found. Check sources and try again.")
        return

    if args.limit:
        raw = raw[: args.limit]
        log.info(f"Capped at {args.limit} events")

    # 2. Enrich + score with Claude
    log.info("Enriching and scoring prospects with Claude...")
    prospects = enrich_prospects(client, raw)

    if not prospects:
        log.warning("No prospects returned from enrichment.")
        return

    # 3. Deduplicate against last run
    previous  = load_previous_prospects()
    prospects = deduplicate(prospects, previous)

    # 4. Write output
    output_path = write_csv(prospects, dry_run=args.dry_run)

    # 5. Print summary
    print_summary(prospects, output_path)

    log.info("BDR Agent complete.")


if __name__ == "__main__":
    main()
