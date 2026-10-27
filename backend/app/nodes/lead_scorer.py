"""
Nodes 5 & 6 — Lead Scorer + CSV/XLSX Delivery (Real Estate vertical)
=====================================================================
Scoring here is tuned for who actually BUYS this list: vendors selling
services or products INTO real estate (coaching, E&O insurance,
marketing/CRM tools, title/escrow partners, loan officer referral
partnerships). For that buyer, an agent/brokerage is a *better* lead
when it looks established, active, sizeable, and reachable — not
necessarily when it has the highest star rating (that matters far less
to a B2B vendor than it would to a consumer choosing an agent).

Score breakdown (100 pts):
  Team / brokerage size ............ 22 pts  (bigger org = bigger deal size)
  Established (years in business) .. 15 pts
  Digital maturity (IDX + site) .... 15 pts  (active, maintained business)
  Reachability ..................... 25 pts  (verified email > catch-all > WhatsApp > phone)
  Specialization clarity ........... 10 pts  (real, positioned practice)
  Social proof (testimonials) ...... 8 pts
  License / compliance detected .... 5 pts
"""
import os, io, csv, logging
from datetime import datetime
from pathlib import Path
from app.agents.state import LeadState

logger = logging.getLogger(__name__)
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "/tmp/leads"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

_TEAM_LABELS = {"brokerage": "Brokerage", "large_team": "Large team",
                "small_team": "Small team", "solo": "Solo agent"}


def email_label(lead: dict) -> str:
    """What the buyer needs to know: can I send to this address?
    Catch-all servers accept any address, so mail to them doesn't bounce — Valid.
    The scorer still ranks a confirmed mailbox above a catch-all one."""
    if not lead.get("primary_email"):
        return ""
    if lead.get("email_verified") or lead.get("email_catchall") or lead.get("email_status") == "valid":
        return "Valid"
    return "Not verified"


# (header, value) — the export is for the person doing outreach, so only
# contact details and what helps them pick who to call first.
EXPORT_COLS = [
    ("Score",             lambda l: l.get("score", 0)),
    ("Name",              lambda l: l.get("name", "")),
    ("Email",             lambda l: l.get("primary_email", "")),
    ("Email status",      email_label),
    ("Phone",             lambda l: l.get("phone", "")),
    ("WhatsApp",          lambda l: f"https://wa.me/{l['whatsapp']}" if l.get("whatsapp") else ""),
    ("Website",           lambda l: l.get("website", "")),
    ("Address",           lambda l: l.get("address", "")),
    ("Google rating",     lambda l: l.get("rating") or ""),
    ("Google reviews",    lambda l: l.get("review_count") or ""),
    ("Team size",         lambda l: _TEAM_LABELS.get(l.get("team_size"), "")),
    ("Specialties",       lambda l: ", ".join(s.replace("_", " ").title() for s in l.get("specializations") or [])),
    ("Years in business", lambda l: l.get("years_in_business") or ""),
]

_TEAM_SIZE_PTS = {"brokerage": 22, "large_team": 17, "small_team": 11, "solo": 6, "unknown": 3}


# ── Scorer ────────────────────────────────────────────────────────────────────

def _score(lead: dict) -> int:
    s = 0

    # Team / brokerage size (22 pts) — bigger org, bigger deal for a B2B vendor
    s += _TEAM_SIZE_PTS.get(lead.get("team_size", "unknown"), 3)

    # Established (15 pts)
    years = int(lead.get("years_in_business") or 0)
    s += 15 if years >= 10 else 10 if years >= 5 else 5 if years >= 2 else 0

    # Digital maturity (15 pts) — active, maintained web presence
    if lead.get("idx_detected"):   s += 10
    if lead.get("website"):        s += 3
    if lead.get("recent_activity"): s += 2

    # Reachability (25 pts) — can you actually reach them. A deliverable email
    # wins; WhatsApp/phone-only leads still count, just for less.
    email_pts = (25 if lead.get("email_verified") else
                 15 if lead.get("email_catchall") else
                 8  if lead.get("email_valid") else 0)
    contact_pts = 10 if lead.get("whatsapp") else 5 if lead.get("phone") else 0
    s += max(email_pts, contact_pts)

    # Specialization clarity (10 pts) — a positioned practice, not a placeholder
    specs = lead.get("specializations") or []
    s += 10 if len(specs) >= 2 else 6 if len(specs) == 1 else 0

    # Social proof (8 pts)
    testi = int(lead.get("testimonial_count") or 0)
    s += 8 if testi >= 5 else 4 if testi >= 1 else 0

    # License / compliance detected (5 pts)
    if lead.get("license_detected"): s += 5

    return min(100, s)


def score_leads_node(state: LeadState) -> LeadState:
    leads = state.get("verified_leads", [])
    scored = sorted(
        [{**l, "score": _score(l)} for l in leads],
        key=lambda l: l["score"], reverse=True,
    )
    high = sum(1 for l in scored if l["score"] >= 70)
    logger.info(f"[scorer] {len(scored)} leads — {high} high-quality (≥70)")
    return {**state, "scored_leads": scored}


# ── Delivery ──────────────────────────────────────────────────────────────────

def _export_rows(scored_leads: list[dict]) -> list[list]:
    return [[fn(l) for _, fn in EXPORT_COLS] for l in scored_leads]


def leads_to_csv_bytes(scored_leads: list[dict]) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([h for h, _ in EXPORT_COLS])
    w.writerows(_export_rows(scored_leads))
    # utf-8-sig adds a BOM — without it Excel opens the file as ANSI and shows
    # Hebrew/Arabic names as gibberish.
    return buf.getvalue().encode("utf-8-sig")


def leads_to_xlsx_bytes(scored_leads: list[dict]) -> bytes:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter

    rows = _export_rows(scored_leads)
    headers = [h for h, _ in EXPORT_COLS]

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Leads"

    hdr_fill = PatternFill("solid", fgColor="0F172A")
    hdr_font = Font(bold=True, color="FFFFFF", size=10)
    for ci, col in enumerate(headers, 1):
        cell = ws.cell(row=1, column=ci, value=col)
        cell.fill = hdr_fill
        cell.font = hdr_font
        cell.alignment = Alignment(horizontal="center")

    g = PatternFill("solid", fgColor="DCFCE7")
    y = PatternFill("solid", fgColor="FEF9C3")
    r = PatternFill("solid", fgColor="FEE2E2")

    for ri, (lead, row) in enumerate(zip(scored_leads, rows), 2):
        score = lead.get("score", 0)
        fill = g if score >= 70 else y if score >= 40 else r
        for ci, value in enumerate(row, 1):
            cell = ws.cell(row=ri, column=ci, value=value)
            cell.fill = fill

    for ci, col in enumerate(headers, 1):
        maxw = max([len(col)] + [len(str(row[ci - 1])) for row in rows[:50]]) + 2
        ws.column_dimensions[get_column_letter(ci)].width = min(maxw, 40)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def export_filename(location: str, created_at: datetime, ext: str) -> str:
    loc = (location or "leads")[:40].replace(" ", "_").replace(",", "").replace("/", "-")
    return f"agentreach_{loc}_{created_at.strftime('%Y%m%d_%H%M%S')}.{ext}"


def deliver_leads_node(state: LeadState) -> LeadState:
    leads = state.get("scored_leads", [])
    now   = datetime.now()

    # CSV
    csv_path = OUTPUT_DIR / export_filename(state.get("location", ""), now, "csv")
    csv_path.write_bytes(leads_to_csv_bytes(leads))
    logger.info(f"[deliver] CSV → {csv_path}  ({len(leads)} rows)")

    # XLSX
    xlsx_path = None
    try:
        xlsx_path = OUTPUT_DIR / export_filename(state.get("location", ""), now, "xlsx")
        xlsx_path.write_bytes(leads_to_xlsx_bytes(leads))
        logger.info(f"[deliver] XLSX → {xlsx_path}")
    except ImportError:
        xlsx_path = None
        logger.warning("[deliver] openpyxl not installed, skipping XLSX")
    except Exception as e:
        xlsx_path = None
        logger.error(f"[deliver] XLSX error: {e}")

    return {
        **state,
        "final_csv_path":  str(csv_path),
        "final_xlsx_path": str(xlsx_path) if xlsx_path else "",
        "status": "done",
    }
