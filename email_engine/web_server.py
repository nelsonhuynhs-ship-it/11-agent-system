# web_server.py — Email Dashboard Server v2
import os, sys, csv, random, logging
from pathlib import Path
from datetime import date, datetime, timedelta
from typing import List, Optional

BASE_DIR = Path(__file__).parent
ENGINE_TEST = BASE_DIR.parent
# Order matters: core/ has a file 'email_engine.py' that shadows the package
# if placed before root. Insert root LAST so it wins (ends up at path[0]).
sys.path.insert(0, str(BASE_DIR / "core"))
sys.path.insert(0, str(ENGINE_TEST))

import pandas as pd
from fastapi import FastAPI, BackgroundTasks, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("email-dash")

try:
    from shared.paths import PARQUET_FILE
except ImportError:
    PARQUET_FILE = ENGINE_TEST / "Pricing_Engine" / "data" / "Cleaned_Master_History.parquet"

# 2026-04-17: load full 28K CNEE from OneDrive canonical file (per data-source-correction
# memory). Previous data.xlsx local was the 5K subset — we want ALL prospects now.
# File order: OneDrive v2_final (newest 28K) > v2 > local 5K fallback.
_ONEDRIVE_EMAIL = Path("D:/OneDrive/NelsonData/email")
_CNEE_CANDIDATES = [
    _ONEDRIVE_EMAIL / "cnee_master_v2_final.xlsx",
    _ONEDRIVE_EMAIL / "cnee_master_v2.xlsx",
    BASE_DIR / "data.xlsx",  # final fallback
]

DATA_FILE   = next((p for p in _CNEE_CANDIDATES if p.exists()), _CNEE_CANDIDATES[-1])
CONFIG_FILE = BASE_DIR / "data" / "config.xlsx"
LOG_FILE    = BASE_DIR / "logs" / "email_log.csv"
CNEE_V2     = _ONEDRIVE_EMAIL / "cnee_master_v2_final.xlsx"
CNEE_V1     = _ONEDRIVE_EMAIL / "cnee_master.xlsx"
(BASE_DIR / "logs").mkdir(exist_ok=True)

SEND_PROGRESS: dict = {}  # campaign_id → {sent, total, errors, status}

log.info(f"Loading contacts from {DATA_FILE}...")
df_contacts = pd.read_excel(DATA_FILE)
df_contacts.columns = df_contacts.columns.str.strip().str.upper()

# Column compatibility: v2_final uses EMAIL/COMPANY/PIC/CAMPAIGN_ID; legacy uses
# CNEE_EMAIL/CNEE_NAME/CNEE_PIC/CMD_NAME. Normalize to legacy names so downstream
# filter/query logic stays unchanged.
_COL_ALIASES = {
    "EMAIL": "CNEE_EMAIL",
    "COMPANY": "CNEE_NAME",
    "PIC": "CNEE_PIC",
    "CAMPAIGN_ID": "CMD_NAME",
}
for src, dst in _COL_ALIASES.items():
    if src in df_contacts.columns and dst not in df_contacts.columns:
        df_contacts[dst] = df_contacts[src]

# Drop rows without email or without campaign — they can't be sent anyway.
df_contacts = df_contacts[df_contacts["CNEE_EMAIL"].notna()]
if "CMD_NAME" in df_contacts.columns:
    df_contacts["CMD_NAME"] = df_contacts["CMD_NAME"].fillna("UNCATEGORIZED").astype(str)
log.info(f"Loaded {len(df_contacts)} contacts, {df_contacts['CMD_NAME'].nunique()} campaigns")

def load_config():
    import openpyxl
    wb = openpyxl.load_workbook(str(CONFIG_FILE), data_only=True)
    cfg = {}
    for row in wb.active.iter_rows(max_col=2, values_only=True):
        k = str(row[0] or "").strip()
        v = str(row[1] or "").strip() if row[1] else ""
        if k and k.lower() != "key":
            cfg[k] = v
            cfg[k.upper()] = v
    return cfg

CFG = load_config()

def gen_subject():
    templates = [t.strip() for t in CFG.get("SUBJECTTEMPLATES", CFG.get("SubjectTemplates", "")).split("|") if t.strip()]
    if not templates:
        templates = ["Asia-US Ocean Freight Update"]
    suffix = CFG.get("SUBJECTSUFFIX", CFG.get("SubjectSuffix", "NELSON"))
    wk = date.today().isocalendar()[1]
    return f"{random.choice(templates)} // {suffix} WEEK {wk}"

class ContactItem(BaseModel):
    email: str
    pic: str = "Team"
    company: str = ""
    pol: str = ""
    dest: str = ""
    force_send: bool = False

class SendRequest(BaseModel):
    contacts: List[ContactItem] = Field(..., min_length=1, max_length=250)
    subject: str = ""
    default_pol: str = "HPH"
    default_dest: str = "USLAX,USLGB,USSAV,USNYC,USORF,USCHS,USTIW,USCHI,USDAL"
    markup: float = Field(default=20.0, ge=0, le=500)
    arb_origin: str = ""  # Optional cross-origin key (e.g. "shanghai")
    preset: str = ""  # Optional preset: "friday_hpl_scfi_hcm" → force POL=HCM + prefer HPL SCFI rates

def err(code: int, msg: str):
    raise HTTPException(status_code=code, detail={"error": msg})

app = FastAPI(title="Email Dashboard v2")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8230", "http://localhost:8231", "http://localhost:3000",
                   "http://127.0.0.1:8230", "http://127.0.0.1:8231", "http://localhost:8100",
                   "http://127.0.0.1:8100", "null"],  # null = file:// origin
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

import re as _re
# Email format cleanup (Nelson 2026-04-17): reject junk prefixes like em@, te@, me@
_EMAIL_BAD_PREFIX = _re.compile(r"^(em|te|me|tel|fax|info|no|noreply|no-reply|unknown|n/?a|null|test|admin|abuse|postmaster|webmaster|hostmaster|mailer-daemon)@", _re.IGNORECASE)
_EMAIL_RX = _re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
_PIC_BAD = {"hi", "hello", "dear", "team", "sir", "madam", "mr", "mrs", "ms", "customer", "to whom it may concern", "n/a", "na", "nan", "none", ""}

# ── Excluded customers (active customers / converted / do-not-contact) ──────
# Stored in email_engine/data/excluded_customers.json so it survives restarts
# and can be edited by Nelson directly (or via /api/customer/exclude).
_EXCLUSION_FILE = BASE_DIR / "data" / "excluded_customers.json"

def _load_exclusions() -> set[str]:
    """Return set of lowercase emails to never contact."""
    try:
        import json as _json
        data = _json.loads(_EXCLUSION_FILE.read_text(encoding="utf-8"))
        return {e.lower().strip() for e in data.get("excluded", {}).keys() if e}
    except Exception:
        return set()

EXCLUDED_EMAILS: set[str] = _load_exclusions()
log.info(f"Excluded customers loaded: {len(EXCLUDED_EMAILS)} emails")

def _reload_exclusions():
    """Re-read the JSON (used after /api/customer/exclude mutates it)."""
    global EXCLUDED_EMAILS
    EXCLUDED_EMAILS = _load_exclusions()

@app.get("/api/customer/excluded")
def list_excluded():
    """List all emails on the do-not-contact list."""
    try:
        import json as _json
        data = _json.loads(_EXCLUSION_FILE.read_text(encoding="utf-8"))
        return {"total": len(data.get("excluded", {})), "excluded": data.get("excluded", {})}
    except Exception as exc:
        return {"total": 0, "excluded": {}, "error": str(exc)}

@app.post("/api/customer/exclude")
def add_excluded(email: str, reason: str = "active customer", company: str = "", campaign: str = "", added_by: str = "API"):
    """Add an email to the permanent do-not-contact list. Affects ALL send endpoints."""
    import json as _json
    em = (email or "").strip().lower()
    if not em or "@" not in em:
        raise HTTPException(400, "invalid email")
    try:
        data = _json.loads(_EXCLUSION_FILE.read_text(encoding="utf-8")) if _EXCLUSION_FILE.exists() else {"excluded": {}}
    except Exception:
        data = {"excluded": {}}
    data.setdefault("excluded", {})[em] = {
        "reason": reason,
        "company": company,
        "campaign": campaign,
        "added_at": datetime.now().strftime("%Y-%m-%d"),
        "added_by": added_by,
    }
    _EXCLUSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    _EXCLUSION_FILE.write_text(_json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    _reload_exclusions()
    # Also try to scrub any pending queue entries for this email
    cleaned_queue = 0
    try:
        import sqlite3 as _sq
        qdb = BASE_DIR / "data" / "outlook_queue.db"
        if qdb.exists():
            con = _sq.connect(str(qdb))
            cur = con.execute("DELETE FROM email_queue WHERE LOWER(cnee_email)=? AND status IN ('pending','sending')", (em,))
            cleaned_queue = cur.rowcount
            con.commit(); con.close()
    except Exception as e:
        log.warning(f"Queue scrub failed: {e}")
    return {"status": "excluded", "email": em, "total_excluded": len(EXCLUDED_EMAILS), "queue_entries_removed": cleaned_queue}

@app.delete("/api/customer/exclude")
def remove_excluded(email: str):
    """Remove an email from the do-not-contact list (re-allow prospecting)."""
    import json as _json
    em = (email or "").strip().lower()
    try:
        data = _json.loads(_EXCLUSION_FILE.read_text(encoding="utf-8"))
    except Exception:
        raise HTTPException(404, "exclusion file missing")
    removed = data.get("excluded", {}).pop(em, None)
    if not removed:
        raise HTTPException(404, f"email '{em}' not in exclusion list")
    _EXCLUSION_FILE.write_text(_json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    _reload_exclusions()
    return {"status": "removed", "email": em, "total_excluded": len(EXCLUDED_EMAILS)}


@app.get("/api/campaigns")
def get_campaigns():
    cmds = df_contacts.groupby("CMD_NAME").size().reset_index(name="count")
    cmds = cmds.sort_values("count", ascending=False)
    result = [{"name": r["CMD_NAME"], "count": int(r["count"])} for _, r in cmds.iterrows()]
    result.insert(0, {"name": "ALL", "count": int(len(df_contacts))})
    return result

def _good_email(e: str) -> bool:
    e = (e or "").strip().lower()
    if not e or not _EMAIL_RX.match(e):
        return False
    if _EMAIL_BAD_PREFIX.match(e):
        return False
    return True

def _pic_is_bad(p: str) -> bool:
    if not p: return True
    p = p.strip()
    return (not p
            or p.lower() in _PIC_BAD
            or len(p) < 2
            or p.isdigit()
            or p[0].isdigit())

def _clean_pic(pic: str, company: str) -> str:
    p = (pic or "").strip()
    if not _pic_is_bad(p):
        return p.title() if p.islower() else p
    # Fallback: first non-numeric word of company, skipping street-address junk
    c = (company or "").strip()
    if c:
        for tok in c.replace(",", " ").split():
            tok = tok.strip(".-_").strip()
            if tok and not tok[0].isdigit() and len(tok) >= 2 and tok.lower() not in {"ltd","llc","inc","corp","co","the","and","of","street","st","ave","avenue","floor","suite","unit"}:
                return tok.title() if tok.islower() else tok
    return "Team"

@app.get("/api/contacts")
def get_contacts(campaign: str):
    subset = df_contacts[df_contacts["CMD_NAME"] == campaign].copy() if campaign != "ALL" else df_contacts.copy()
    subset = subset[subset["CNEE_EMAIL"].notna()]
    subset["_el"] = subset["CNEE_EMAIL"].astype(str).str.lower().str.strip()
    subset = subset.drop_duplicates(subset="_el")

    results = []
    dropped_bad_email = 0
    for _, row in subset.iterrows():
        def clean(field, default=""):
            v = str(row.get(field, "")).strip()
            return default if v.lower() in ("nan", "") else v
        email = clean("CNEE_EMAIL")
        if not _good_email(email):
            dropped_bad_email += 1
            continue
        if email.lower() in EXCLUDED_EMAILS:
            continue  # active customer / opt-out — never contact
        company = clean("CNEE_NAME")
        results.append({
            "email": email,
            "pic": _clean_pic(clean("CNEE_PIC"), company),
            "company": company,
            "pol": clean("POL"),
            "dest": clean("DESTINATION"),
        })
    results.sort(key=lambda x: x["company"])
    return {"contacts": results, "subject": gen_subject(), "total": len(results), "dropped_bad_email": dropped_bad_email}

@app.get("/api/rate-preview")
def rate_preview(pol: str, destinations: str, markup: float = 20.0, arb_origin: str = None):
    from auto_rate_builder import build_rate_table_for_customer
    try:
        return build_rate_table_for_customer(
            pol=pol, destinations=destinations, markup=markup,
            arb_origin=arb_origin or None,
        )
    except Exception as e:
        log.warning(f"Rate preview failed: {e}")
        return {"routes_found": 0, "total_rates": 0, "html": "", "routes_detail": []}


@app.get("/api/arb-rates")
def get_arb_rates():
    """Return all available ARB origins, carriers, and sample rates from YAML."""
    try:
        from arb_pricing import load_arb_rates, get_available_origins
        rates = load_arb_rates()
        origins = get_available_origins()
        return {"origins": origins, "raw": rates}
    except Exception as e:
        log.warning(f"ARB rates load failed: {e}")
        return {"origins": [], "raw": {}}

def _log_send(email, subj, cid, pol, dest):
    exists = LOG_FILE.exists()
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if not exists:
            w.writerow(["timestamp","email","subject","campaign_id","cycle_id","status","pol","dest"])
        w.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), email, subj, cid, "1", "SENT", pol, dest])

def _load_cooldown_map() -> dict:
    """Load email_log.csv and return {email: last_datetime} for cooldown checks."""
    if not LOG_FILE.exists():
        return {}
    try:
        df = pd.read_csv(LOG_FILE, usecols=["timestamp", "email"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        return df.dropna().groupby("email")["timestamp"].max().to_dict()
    except Exception:
        return {}

def _do_send(campaign_id: str, req: SendRequest):
    from auto_rate_builder import build_rate_table_for_customer
    prog = SEND_PROGRESS[campaign_id]
    prog["status"] = "running"

    try:
        import win32com.client
        outlook = win32com.client.Dispatch("Outlook.Application")
    except Exception as e:
        prog["status"] = "failed"
        prog["errors"].append({"email": "outlook", "error": str(e)})
        return

    default_intro = CFG.get("INTROTEXT", CFG.get("IntroText", ""))
    closing   = CFG.get("CLOSINGTEXT", CFG.get("ClosingText", ""))
    signature = CFG.get("SIGNATURE", CFG.get("Signature", ""))
    cooldown_map = _load_cooldown_map()
    cutoff = datetime.now() - pd.Timedelta(hours=48)

    # AI-powered intro templates (fallback to config.xlsx default)
    AI_INTROS = {
        "URGENT": "Rates are trending upward — we recommend securing your booking soon to lock current pricing.",
        "COMPETITIVE": "Market rates have softened recently — great timing to explore competitive options on this lane.",
        "STABLE": default_intro,  # keep config.xlsx intro for stable market
    }

    # Build suppression set from cnee_master_v2 EMAIL_STATUS
    suppressed_emails: set = set()
    SUPPRESSED_STATUSES = {"HARD_BOUNCE", "INVALID", "NO_MX"}
    try:
        cnee_src = CNEE_V2 if CNEE_V2.exists() else (CNEE_V1 if CNEE_V1.exists() else None)
        if cnee_src:
            _cnee = pd.read_excel(cnee_src, usecols=["EMAIL", "EMAIL_STATUS"])
            _cnee.columns = _cnee.columns.str.upper()
            _bad = _cnee[_cnee["EMAIL_STATUS"].isin(SUPPRESSED_STATUSES)]
            suppressed_emails = set(_bad["EMAIL"].astype(str).str.lower().str.strip())
            log.info(f"Suppression list loaded: {len(suppressed_emails)} emails")
    except Exception as ex:
        log.warning(f"Could not load suppression list: {ex}")

    for c in req.contacts:
        em_lower = c.email.strip().lower()
        # Excluded customers (active / opt-out) — ALWAYS skip, even with force_send
        if em_lower in EXCLUDED_EMAILS:
            prog["skipped"] = prog.get("skipped", 0) + 1
            log.info(f"EXCLUDED -> {c.email} (active customer)")
            continue
        # Suppression check: skip hard bounced / invalid / no-MX emails
        if em_lower in suppressed_emails and not c.force_send:
            prog["skipped"] = prog.get("skipped", 0) + 1
            log.info(f"SUPPRESSED -> {c.email}")
            continue

        # Cooldown check: skip if sent within last 48 hours
        last_sent = cooldown_map.get(c.email.strip().lower())
        if last_sent and last_sent > cutoff and not c.force_send:
            prog["skipped_cooldown"] = prog.get("skipped_cooldown", 0) + 1
            log.info(f"COOLDOWN -> {c.email} (last: {last_sent})")
            continue
        try:
            # Preset mode override (Mode 2 per Nelson 2026-04-17):
            #   "friday_hpl_scfi_hcm" → force POL=HCM, builder auto prefers HPL SCFI
            #   lanes from HCM (the Friday SCFI release).
            if req.preset == "friday_hpl_scfi_hcm":
                pol = "HCM"
                dest = c.dest or req.default_dest
            else:
                pol = c.pol or req.default_pol
                dest = c.dest or req.default_dest
            # Hard fallback so builder never sees empty/NaN destinations
            if not dest or str(dest).lower() in ("nan", "none", ""):
                dest = "USLAX,USLGB,USSAV,USNYC,USORF,USCHS,USTIW,USCHI,USDAL"
            # Clean PIC so "Dear Hi," / "Dear Team," never leaks out
            pic = _clean_pic(getattr(c, "pic", ""), getattr(c, "company", ""))
            c.pic = pic  # write back so downstream template uses clean value
            result = build_rate_table_for_customer(
                pol=pol, destinations=dest, markup=req.markup,
                arb_origin=req.arb_origin or None,
            )
            html = result.get("html", "")
            if not html and not c.force_send:
                prog["skipped"] = prog.get("skipped", 0) + 1
                continue

            # Pick intro based on AI market context (if model loaded)
            mkt = result.get("market_context")
            if AI_MODEL and mkt:
                intro = AI_INTROS.get(mkt.get("template_type", "STABLE"), default_intro)
            else:
                intro = default_intro

            subj = req.subject or gen_subject()
            # Skip if auto-rate builder produced no real lanes — avoid empty "NAN" emails
            if not html or "No rates available" in html:
                prog["skipped"] = prog.get("skipped", 0) + 1
                log.info(f"SKIP (no rates) -> {c.email}")
                continue
            m = outlook.CreateItem(0)
            m.To = c.email
            m.Subject = subj
            body = f"<p>Dear {pic},</p><p>{intro}</p>{html}<br><p>{closing}</p>"
            if signature:
                body += f"<br>{signature}"
            m.HTMLBody = f"<html><body>{body}</body></html>"
            m.Send()
            prog["sent"] += 1
            _log_send(c.email, subj, campaign_id, pol, dest)
            log.info(f"SENT -> {c.email} ({pol}→{dest})")
        except Exception as e:
            prog["errors"].append({"email": c.email, "error": str(e)})
            log.error(f"FAIL -> {c.email}: {e}")

    prog["status"] = "done"

@app.post("/api/send", status_code=202)
def send_emails(req: SendRequest, background_tasks: BackgroundTasks):
    campaign_id = f"DASH_{datetime.now():%Y%m%d_%H%M%S}"
    SEND_PROGRESS[campaign_id] = {"sent": 0, "total": len(req.contacts), "errors": [], "status": "queued", "skipped_cooldown": 0}
    background_tasks.add_task(_do_send, campaign_id, req)
    return {"campaign_id": campaign_id, "total": len(req.contacts), "status": "queued"}

@app.get("/api/send-status/{campaign_id}")
def send_status(campaign_id: str):
    prog = SEND_PROGRESS.get(campaign_id)
    if prog is None:
        err(404, f"campaign_id '{campaign_id}' not found")
    return {"campaign_id": campaign_id, **prog}

@app.get("/api/history")
def get_history(limit: int = 100, email: str = None, campaign_id: str = None):
    if not LOG_FILE.exists():
        return []
    df = pd.read_csv(LOG_FILE)
    if email:
        df = df[df["email"].str.lower() == email.strip().lower()]
    if campaign_id:
        df = df[df["campaign_id"] == campaign_id]
    return df.sort_values("timestamp", ascending=False).head(limit).to_dict(orient="records")

@app.get("/api/history/stats")
def get_history_stats():
    if not LOG_FILE.exists():
        return {"total_sent_today": 0, "total_sent_week": 0, "unique_recipients_today": 0, "top_campaigns": []}
    df = pd.read_csv(LOG_FILE)
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["timestamp"])
    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start  = pd.Timestamp(now) - pd.Timedelta(days=7)
    today_df = df[df["timestamp"] >= today_start]
    week_df  = df[df["timestamp"] >= week_start]
    top = (df.groupby("campaign_id").size().reset_index(name="count")
             .sort_values("count", ascending=False).head(5))
    return {
        "total_sent_today":        int(len(today_df)),
        "total_sent_week":         int(len(week_df)),
        "unique_recipients_today": int(today_df["email"].nunique()),
        "top_campaigns":           top.to_dict(orient="records"),
    }

@app.get("/api/config")
def get_config():
    return {
        "subject": gen_subject(),
        "intro": CFG.get("INTROTEXT", CFG.get("IntroText", "")),
        "closing": CFG.get("CLOSINGTEXT", CFG.get("ClosingText", "")),
        "week": date.today().isocalendar()[1],
    }

# ── Email Verification ────────────────────────────────────────────
VERIFY_PROGRESS: dict = {"running": False, "current": 0, "total": 0, "status": "idle", "results": {}}

@app.post("/api/verify-emails")
def verify_emails(background_tasks: BackgroundTasks, smtp: bool = False):
    if VERIFY_PROGRESS["running"]:
        return {"error": "Verification already running", "progress": VERIFY_PROGRESS}
    VERIFY_PROGRESS.update({"running": True, "current": 0, "total": 0, "status": "starting", "results": {}})
    def _run():
        try:
            from email_bulk_verifier import bulk_verify
            def _cb(cur, tot, email, status):
                VERIFY_PROGRESS["current"] = cur
                VERIFY_PROGRESS["total"] = tot
                VERIFY_PROGRESS["status"] = f"{cur}/{tot}"
            result = bulk_verify(smtp=smtp, progress_callback=_cb)
            VERIFY_PROGRESS["results"] = result
            VERIFY_PROGRESS["status"] = "done"
        except Exception as e:
            VERIFY_PROGRESS["status"] = f"error: {e}"
            VERIFY_PROGRESS["results"] = {"error": str(e)}
        finally:
            VERIFY_PROGRESS["running"] = False
    background_tasks.add_task(_run)
    return {"message": "Verification started", "smtp": smtp}

@app.get("/api/verify-emails/progress")
def verify_progress():
    return VERIFY_PROGRESS

@app.get("/api/data-health")
def data_health():
    """Returns contact quality stats from cnee_master_v2 (falls back to v1)."""
    cnee_src = CNEE_V2 if CNEE_V2.exists() else (CNEE_V1 if CNEE_V1.exists() else None)
    if not cnee_src:
        return {"error": "cnee_master not found", "total_contacts": 0}
    try:
        df = pd.read_excel(cnee_src)
        df.columns = df.columns.str.strip().str.upper()
        total = len(df)
        statuses = df.get("EMAIL_STATUS", pd.Series(["VALID"] * total))
        valid = int((statuses == "VALID").sum())
        bounced = int(statuses.isin(["HARD_BOUNCE", "SOFT_BOUNCE", "SOFT_SUPPRESSED"]).sum())
        invalid = int(statuses.isin(["INVALID", "NO_MX"]).sum())
        missing_pol = int(df["POL"].isna().sum() if "POL" in df.columns else 0)
        missing_dest = int(df["DESTINATION"].isna().sum() if "DESTINATION" in df.columns else 0)
        missing_phone = int(
            (df["PHONE"].isna() | (df["PHONE"].astype(str).str.strip() == "")).sum()
            if "PHONE" in df.columns else total
        )
        return {
            "source": cnee_src.name,
            "total_contacts": total,
            "valid_emails": valid,
            "bounced": bounced,
            "invalid": invalid,
            "missing_pol": missing_pol,
            "missing_dest": missing_dest,
            "missing_phone": missing_phone,
        }
    except Exception as e:
        log.error(f"data-health error: {e}")
        return {"error": str(e)}

# ── AI Model Endpoints ─────────────────────────────────────────
# ── Auto-load saved model on startup ───────────────────────────
from rate_predictor import load_model, get_model_status
AI_MODEL: dict = load_model() or {}
if AI_MODEL:
    log.info(f"AI Model loaded from disk (trained: {AI_MODEL.get('trained_at', '?')})")
else:
    log.info("No saved AI model found — click Train Model in dashboard")

@app.get("/api/market-snapshot")
def market_snapshot():
    from rate_predictor import get_market_snapshot
    return get_market_snapshot()

@app.get("/api/model-status")
def model_status():
    from rate_predictor import get_model_status
    status = get_model_status()
    status["loaded_in_memory"] = bool(AI_MODEL)
    return status

@app.post("/api/train-model")
def train_model_endpoint(background_tasks: BackgroundTasks):
    global AI_MODEL
    from rate_predictor import extract_features, train_model, benchmark as bm, FEATURE_COLS, save_model
    try:
        df = extract_features()
        model = train_model(df)
        if not model:
            err(500, "Training failed — insufficient data")
        grades = bm(model["metrics"])
        AI_MODEL = model
        save_model(model)  # Persist to disk
        # Build feature importance with values from XGBoost
        clf = model["model_direction"]
        fi_names = model.get("feature_importance", [])
        fi_vals = dict(zip(FEATURE_COLS, clf.feature_importances_)) if hasattr(clf, 'feature_importances_') else {}
        fi_list = [{"name": n, "value": round(float(fi_vals.get(n, 0)) * 100, 1)} for n in fi_names]
        return {"metrics": model["metrics"], "benchmark": grades,
                "feature_importance": fi_list,
                "walk_forward_results": model.get("walk_forward_results", [])}
    except Exception as e:
        log.error(f"Train failed: {e}")
        err(500, str(e))

@app.get("/api/predict")
def predict_endpoint():
    if not AI_MODEL:
        err(400, "Model not trained yet — click Train Model first")
    from rate_predictor import extract_features, predict as pred
    df = extract_features()
    latest = df.sort_values("week").groupby("corridor").last().reset_index()
    # Predict ALL key corridors
    predictions = []
    for _, row in latest.iterrows():
        try:
            r = pred(AI_MODEL, row)
            r["corridor"] = row["corridor"]
            r["current_fak"] = round(float(row["fak_avg"]), 0) if pd.notna(row["fak_avg"]) else None
            predictions.append(r)
        except Exception:
            pass
    # Sort: highest confidence first
    predictions.sort(key=lambda x: x.get("confidence", 0), reverse=True)
    # Summary: majority vote
    dirs = [p["direction"] for p in predictions]
    majority = max(set(dirs), key=dirs.count) if dirs else "STABLE"
    avg_conf = sum(p.get("confidence", 0) for p in predictions) / max(len(predictions), 1)
    return {"overall_direction": majority, "overall_confidence": round(avg_conf, 3),
            "corridors": predictions, "total_corridors": len(predictions)}

# ── Phase 2: Sequence / Reply / Lead Scoring Endpoints ────────────
@app.get("/api/sequence/due")
def sequence_due(campaign: str = None):
    """Return contacts due for next follow-up step."""
    try:
        from sequence_runner import get_due_contacts
        contacts = get_due_contacts(campaign_id=campaign)
        return {"due": contacts, "count": len(contacts)}
    except Exception as e:
        log.error(f"sequence/due error: {e}")
        return {"due": [], "count": 0, "error": str(e)}


class SequenceSendRequest(BaseModel):
    campaign_id: str = ""
    dry_run: bool = False


@app.post("/api/sequence/send", status_code=202)
def sequence_send(req: SequenceSendRequest, background_tasks: BackgroundTasks):
    """Send follow-up emails for all due contacts (background task)."""
    from sequence_runner import get_due_contacts, advance_step, get_template

    due = get_due_contacts(campaign_id=req.campaign_id or None)
    if not due:
        return {"queued": 0, "message": "No contacts due for follow-up"}

    def _send_followups():
        try:
            import win32com.client
            outlook = win32com.client.Dispatch("Outlook.Application")
        except Exception as e:
            log.error(f"Outlook unavailable for sequence send: {e}")
            return

        signature = CFG.get("SIGNATURE", CFG.get("Signature", ""))
        sent = 0
        for c in due:
            if req.dry_run:
                log.info(f"[DRY] SEQ step {c['next_step']} -> {c['email']}")
                sent += 1
                continue
            try:
                m = outlook.CreateItem(0)
                m.To = c["email"]
                m.Subject = c["subject"]
                body = f"<html><body><p>Dear Team,</p><p>{c['intro']}</p><br>{signature}</body></html>"
                m.HTMLBody = body
                m.Send()
                advance_step(c["email"], c["next_step"])
                _log_send(c["email"], c["subject"], c.get("campaign_id", "SEQ"), "", "")
                log.info(f"SEQ SENT step {c['next_step']} -> {c['email']}")
                sent += 1
            except Exception as e:
                log.error(f"SEQ FAIL -> {c['email']}: {e}")

        log.info(f"Sequence send done: {sent}/{len(due)} emails sent")

    background_tasks.add_task(_send_followups)
    return {"queued": len(due), "status": "running", "dry_run": req.dry_run}


@app.get("/api/replies/scan")
def replies_scan(hours_back: int = 24):
    """Scan Outlook inbox for replies, update master, return count."""
    try:
        from reply_detector import scan_replies, process_replies
        replies = scan_replies(hours_back=hours_back)
        count = process_replies(replies)
        return {"new_replies": count, "scanned": len(replies), "hours_back": hours_back}
    except Exception as e:
        log.error(f"replies/scan error: {e}")
        return {"new_replies": 0, "scanned": 0, "error": str(e)}


@app.get("/api/leads/hot")
def leads_hot(days: int = 7):
    """Return contacts who replied within last N days, sorted by LEAD_SCORE."""
    try:
        from reply_detector import get_hot_leads
        leads = get_hot_leads(days=days)
        return {"leads": leads, "count": len(leads), "days": days}
    except Exception as e:
        log.error(f"leads/hot error: {e}")
        return {"leads": [], "count": 0, "error": str(e)}


@app.get("/api/leads/priority")
def leads_priority(campaign: str = "", top: int = 50):
    """Return top N contacts by LEAD_SCORE for a campaign."""
    try:
        from lead_scorer import get_priority_contacts
        contacts = get_priority_contacts(campaign_id=campaign, top_n=top)
        return {"contacts": contacts, "count": len(contacts), "campaign": campaign}
    except Exception as e:
        log.error(f"leads/priority error: {e}")
        return {"contacts": [], "count": 0, "error": str(e)}


# ── WhatsApp Endpoints ─────────────────────────────────────────
try:
    from whatsapp_sender import (
        is_configured as wa_is_configured, bulk_send_templates, TEMPLATE_NAMES,
    )
    from whatsapp_webhook import verify_webhook, process_webhook
    WA_ENABLED = True
except ImportError:
    WA_ENABLED = False
    log.warning("WhatsApp modules not found — WA endpoints disabled")

class WASendRequest(BaseModel):
    campaign_id: str
    template_name: str
    limit: int = Field(default=100, ge=1, le=1000)

@app.get("/api/whatsapp/status")
def wa_status():
    configured = WA_ENABLED and wa_is_configured()
    wa_log_path = BASE_DIR / "logs" / "whatsapp_log.csv"
    sent = failed = 0
    if wa_log_path.exists():
        try:
            wdf = pd.read_csv(wa_log_path)
            sent   = int((wdf["status"] == "SENT").sum())
            failed = int(wdf["status"].isin(["FAILED", "INVALID_PHONE"]).sum())
        except Exception:
            pass
    return {"configured": configured, "wa_enabled": WA_ENABLED,
            "total_sent": sent, "total_failed": failed}

@app.post("/api/whatsapp/send")
def wa_send(req: WASendRequest):
    if not WA_ENABLED or not wa_is_configured():
        raise HTTPException(status_code=503, detail={"error": "WhatsApp not configured"})
    if req.template_name not in TEMPLATE_NAMES:
        raise HTTPException(status_code=400, detail={"error": f"Unknown template: {req.template_name}"})
    cnee_src = CNEE_V2 if CNEE_V2.exists() else (CNEE_V1 if CNEE_V1.exists() else None)
    if not cnee_src:
        raise HTTPException(status_code=404, detail={"error": "cnee_master not found"})
    try:
        cdf = pd.read_excel(cnee_src)
        cdf.columns = cdf.columns.str.strip().str.upper()
        if "CMD_NAME" in cdf.columns:
            cdf = cdf[cdf["CMD_NAME"] == req.campaign_id]
        cdf = cdf.head(req.limit)
        result = bulk_send_templates(cdf, req.template_name)
        return result
    except Exception as e:
        log.error(f"WA bulk send error: {e}")
        raise HTTPException(status_code=500, detail={"error": str(e)})

@app.get("/api/whatsapp/webhook")
def wa_webhook_verify(
    hub_mode: str = None, hub_verify_token: str = None, hub_challenge: str = None
):
    if not WA_ENABLED:
        raise HTTPException(status_code=503, detail="WhatsApp not enabled")
    from fastapi.responses import PlainTextResponse
    challenge = verify_webhook(hub_mode or "", hub_verify_token or "", hub_challenge or "")
    if challenge is None:
        raise HTTPException(status_code=403, detail="Webhook verification failed")
    return PlainTextResponse(challenge)

@app.post("/api/whatsapp/webhook", status_code=200)
def wa_webhook_receive(payload: dict):
    if not WA_ENABLED:
        return {"ok": True}
    try:
        count = process_webhook(payload)
        return {"ok": True, "processed": count}
    except Exception as e:
        log.error(f"Webhook processing error: {e}")
        return {"ok": True}  # always 200 to Meta

# ── Analytics Endpoints ───────────────────────────────────────────
_analytics_cache: dict = {}
_analytics_cache_ts: float = 0.0
_ANALYTICS_TTL = 60  # seconds

def _load_email_log() -> "pd.DataFrame":
    if not LOG_FILE.exists():
        return pd.DataFrame(columns=["timestamp","email","subject","campaign_id","status","reply_timestamp","cycle_id"])
    df = pd.read_csv(LOG_FILE)
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    return df.dropna(subset=["timestamp"])

def _load_cnee() -> "pd.DataFrame":
    src = CNEE_V2 if CNEE_V2.exists() else (CNEE_V1 if CNEE_V1.exists() else None)
    if not src:
        return pd.DataFrame()
    df = pd.read_excel(src)
    df.columns = df.columns.str.strip().str.upper()
    return df

@app.get("/api/analytics/overview")
def analytics_overview():
    import time
    global _analytics_cache, _analytics_cache_ts
    now = time.time()
    if _analytics_cache.get("overview") and now - _analytics_cache_ts < _ANALYTICS_TTL:
        return _analytics_cache["overview"]
    try:
        df = _load_email_log()
        cnee = _load_cnee()
        today_start = pd.Timestamp.now().normalize()
        wa_log_path = BASE_DIR / "logs" / "whatsapp_log.csv"
        wa_today = 0
        if wa_log_path.exists():
            try:
                wdf = pd.read_csv(wa_log_path)
                wdf["timestamp"] = pd.to_datetime(wdf["timestamp"], errors="coerce")
                wa_today = int((wdf["timestamp"] >= today_start).sum())
            except Exception:
                pass
        total_sent = len(df)
        total_contacts = len(cnee) if not cnee.empty else 0
        campaigns_active = df["campaign_id"].nunique() if "campaign_id" in df.columns else 0
        emails_today = int((df["timestamp"] >= today_start).sum())
        # Reply rate from reply_timestamp column if present
        reply_rate = 0.0
        if "reply_timestamp" in df.columns and total_sent > 0:
            replied = df["reply_timestamp"].notna().sum()
            reply_rate = round(float(replied) / total_sent * 100, 2)
        # Bounce rate from cnee
        bounce_rate = 0.0
        if not cnee.empty and "EMAIL_STATUS" in cnee.columns:
            bounced = cnee["EMAIL_STATUS"].isin(["HARD_BOUNCE","SOFT_BOUNCE"]).sum()
            if total_contacts:
                bounce_rate = round(float(bounced) / total_contacts * 100, 2)
        # Avg lead score
        avg_lead_score = 0
        if not cnee.empty and "LEAD_SCORE" in cnee.columns:
            avg_lead_score = int(cnee["LEAD_SCORE"].dropna().mean() or 0)
        result = {
            "total_sent": total_sent,
            "total_contacts": total_contacts,
            "campaigns_active": campaigns_active,
            "emails_today": emails_today,
            "wa_today": wa_today,
            "reply_rate": reply_rate,
            "bounce_rate": bounce_rate,
            "avg_lead_score": avg_lead_score,
        }
        _analytics_cache["overview"] = result
        _analytics_cache_ts = now
        return result
    except Exception as e:
        log.error(f"analytics/overview error: {e}")
        return {"total_sent":0,"total_contacts":0,"campaigns_active":0,"emails_today":0,"wa_today":0,"reply_rate":0.0,"bounce_rate":0.0,"avg_lead_score":0}

@app.get("/api/analytics/campaign-stats")
def analytics_campaign_stats():
    try:
        df = _load_email_log()
        cnee = _load_cnee()
        if df.empty:
            return []
        # Group by campaign
        grp = df.groupby("campaign_id")
        stats = []
        for cid, sub in grp:
            sent = len(sub)
            replied = int(sub["reply_timestamp"].notna().sum()) if "reply_timestamp" in sub.columns else 0
            reply_rate = round(replied / sent * 100, 1) if sent else 0.0
            # Bounced from cnee filtered to campaign
            bounced = 0
            avg_score = 0
            if not cnee.empty:
                if "CMD_NAME" in cnee.columns:
                    csub = cnee[cnee["CMD_NAME"] == cid]
                else:
                    csub = cnee
                if "EMAIL_STATUS" in csub.columns:
                    bounced = int(csub["EMAIL_STATUS"].isin(["HARD_BOUNCE","SOFT_BOUNCE"]).sum())
                if "LEAD_SCORE" in csub.columns and len(csub):
                    avg_score = int(csub["LEAD_SCORE"].dropna().mean() or 0)
            stats.append({
                "campaign": str(cid),
                "sent": sent,
                "replied": replied,
                "bounced": bounced,
                "reply_rate": reply_rate,
                "avg_score": avg_score,
            })
        stats.sort(key=lambda x: x["reply_rate"], reverse=True)
        return stats
    except Exception as e:
        log.error(f"analytics/campaign-stats error: {e}")
        return []

@app.get("/api/analytics/timeline")
def analytics_timeline(days: int = 30):
    try:
        df = _load_email_log()
        wa_log_path = BASE_DIR / "logs" / "whatsapp_log.csv"
        cutoff = pd.Timestamp.now() - pd.Timedelta(days=days)
        # Email daily
        email_daily: dict = {}
        reply_daily: dict = {}
        if not df.empty:
            recent = df[df["timestamp"] >= cutoff].copy()
            recent["date"] = recent["timestamp"].dt.date.astype(str)
            email_daily = recent.groupby("date").size().to_dict()
            if "reply_timestamp" in recent.columns:
                r = recent[recent["reply_timestamp"].notna()].copy()
                r["rdate"] = pd.to_datetime(r["reply_timestamp"], errors="coerce").dt.date.astype(str)
                reply_daily = r.groupby("rdate").size().to_dict()
        # WA daily
        wa_daily: dict = {}
        if wa_log_path.exists():
            try:
                wdf = pd.read_csv(wa_log_path)
                wdf["timestamp"] = pd.to_datetime(wdf["timestamp"], errors="coerce")
                wdf = wdf[wdf["timestamp"] >= cutoff].copy()
                wdf["date"] = wdf["timestamp"].dt.date.astype(str)
                wa_daily = wdf.groupby("date").size().to_dict()
            except Exception:
                pass
        # Build date range
        import datetime as dt_mod
        result = []
        for i in range(days):
            d = (pd.Timestamp.now() - pd.Timedelta(days=days-1-i)).date()
            ds = str(d)
            result.append({
                "date": ds,
                "emails": email_daily.get(ds, 0),
                "whatsapp": wa_daily.get(ds, 0),
                "replies": reply_daily.get(ds, 0),
            })
        return result
    except Exception as e:
        log.error(f"analytics/timeline error: {e}")
        return []

@app.get("/api/whatsapp/log")
def wa_log_endpoint(limit: int = 100):
    wa_log_path = BASE_DIR / "logs" / "whatsapp_log.csv"
    if not wa_log_path.exists():
        return []
    df = pd.read_csv(wa_log_path)
    return df.sort_values("timestamp", ascending=False).head(limit).to_dict(orient="records")


# ── v4 Dashboard Compatibility Endpoints ──────────────────────────────────────
# These map the v4 dashboard's expected API shape onto web_server's send logic.
# Outlook COM is called directly — no queue, no worker needed.

# ──────────────────────────────────────────────────────────────────
# CNEE master cache — load Excel ONCE per mtime.
# Without this, every /prospects request re-reads a 15MB xlsx file
# (2-3s per request). Dashboard uses 10s timeout → fetch fails →
# dashboard falls back to demo mode even though API is live.
# ──────────────────────────────────────────────────────────────────
_CNEE_CACHE: dict = {"mtime": 0.0, "df": None, "path": None}


def _get_cnee_df():
    """Return cached CNEE dataframe. Reloads if xlsx mtime changed."""
    cnee_src = CNEE_V2 if CNEE_V2.exists() else (CNEE_V1 if CNEE_V1.exists() else None)
    if not cnee_src:
        return None
    try:
        mtime = cnee_src.stat().st_mtime
    except Exception:
        mtime = 0.0
    if (
        _CNEE_CACHE.get("mtime") == mtime
        and _CNEE_CACHE.get("path") == str(cnee_src)
        and _CNEE_CACHE.get("df") is not None
    ):
        return _CNEE_CACHE["df"]
    log.info(f"Loading CNEE master: {cnee_src.name} ({cnee_src.stat().st_size/1024/1024:.1f} MB)")
    df = pd.read_excel(cnee_src)
    df.columns = df.columns.str.strip().str.upper()
    _CNEE_CACHE["mtime"] = mtime
    _CNEE_CACHE["df"] = df
    _CNEE_CACHE["path"] = str(cnee_src)
    log.info(f"CNEE master cached: {len(df):,} rows")
    return df


@app.get("/api/email-rate/campaign/prospects")
def v4_prospects(campaign: str = "", pol: str = "", destination: str = "",
                 sent_status: str = "", page_size: int = 500, markup: float = 20.0):
    """Return prospect list WITH rates (via market_engine, batched per unique lane).

    Perf strategy:
      1. Excel loaded ONCE via _get_cnee_df() cache (mtime-invalidated).
      2. For each row: split DESTINATION column (may be "USLAX,USLGB") → pick
         first or match input 'destination' query.
      3. Collect UNIQUE (pol, pod) pairs from all rows.
      4. Call market_engine.analyze_lane() ONCE per unique pair — results are
         cached 30 min in market_engine itself, so repeat clicks are instant.
         Typical: 500 prospects → 3-5 unique lanes → 3-5 analyze_lane calls.
      5. Apply markup + 20GP estimate (40HQ × 0.78 industry ratio) per contact.

    Before (old code): 500 × build_rate_table_for_customer() per-row → 50s timeout.
    After: ~1.5s cold, <0.3s warm. Dashboard fetch succeeds → Live mode.
    """
    df = _get_cnee_df()
    if df is None:
        return {"prospects": [], "total": 0}

    if campaign and campaign.upper() != "ALL":
        df = df[df.get("CAMPAIGN_ID", df.get("CMD_NAME", pd.Series())).astype(str).str.upper() == campaign.upper()]
    # POL filter: keep rows matching POL OR missing POL (will fallback to default).
    # Strict POL filter drops 90%+ of 28K CNEE whose POL column is empty/NAN.
    if pol and "POL" in df.columns:
        pol_up = pol.upper()
        row_pol = df["POL"].astype(str).str.upper().str.strip()
        df = df[row_pol.isin([pol_up, "", "NAN", "NONE"])]

    cooldown_map = _load_cooldown_map()
    cutoff = datetime.now() - pd.Timedelta(hours=48)

    # ── First pass: build prospect rows + collect unique (pol, pod) lanes ──
    prospects = []
    lanes_needed: set[tuple[str, str]] = set()
    requested_dest = destination.strip().upper() if destination else ""

    # Requested POL (from query param) — used when row's POL is empty/NaN
    requested_pol = (pol or "HPH").strip().upper() or "HPH"

    for i, row in df.head(page_size).iterrows():
        email = str(row.get("EMAIL", row.get("CNEE_EMAIL", ""))).strip()
        if not email or email.lower() == "nan":
            continue
        if email.lower() in EXCLUDED_EMAILS:
            continue  # active customer — do not contact
        # Normalize NaN string (pandas reads empty → "nan") → fallback to requested POL
        row_pol = str(row.get("POL", "")).strip().upper()
        if not row_pol or row_pol in ("NAN", "NONE"):
            row_pol = requested_pol

        # DESTINATION may contain "USLAX,USLGB" — pick best match; fallback to defaults
        row_dest_raw = str(row.get("DESTINATION", "")).strip()
        if row_dest_raw.lower() in ("", "nan", "none"):
            row_dest_raw = ""
        pod_list = [d.strip().upper() for d in row_dest_raw.replace(";", ",").split(",") if d.strip() and d.strip().lower() not in ("nan", "none")]
        if requested_dest and requested_dest in pod_list:
            pod = requested_dest
        elif pod_list:
            pod = pod_list[0]
        else:
            pod = requested_dest or "USLAX"
            pod_list = DEFAULT_DESTINATIONS.copy()  # so multi-POD email gets all 9 lanes

        lanes_needed.add((row_pol, pod))

        last_sent = cooldown_map.get(email.lower())
        in_cooldown = bool(last_sent and last_sent > cutoff)
        already_sent = str(row.get("ALREADY_SENT", "N")).strip().upper()

        prospects.append({
            "id": int(i) if not isinstance(i, int) else i,
            "email": email,
            "company": str(row.get("CNEE_NAME", row.get("COMPANY", ""))).strip(),
            "pol": row_pol,
            "destination": pod,
            "destinations_all": pod_list,  # full list for multi-POD rendering
            "campaign_id": str(row.get("CAMPAIGN_ID", row.get("CMD_NAME", campaign))).strip(),
            "already_sent": already_sent,
            "rate_20": 0,       # filled in second pass
            "rate_40": 0,       # filled in second pass
            "tier": str(row.get("TIER", "")).strip(),
            "in_cooldown": in_cooldown,
        })

    # ── Second pass: compute rates using auto_rate_builder (proven correct) ──
    # auto_rate_builder.build_rate_table_for_customer() uses proper Place/POD
    # mapping + carrier rules + Exp >= today filter. market_engine.analyze_lane()
    # was matching INLAND rates (USLAX → Nashville) as PORT rates → inflated.
    # Batch: 1 call per unique (pol, dest) — typically 3-5 calls, ~500ms total.
    lane_rates: dict[tuple[str, str], dict] = {}
    # Batch all unique destinations into 1 auto_rate_builder call (it handles multi-dest)
    all_dests = list({lane[1] for lane in lanes_needed})
    all_pols = list({lane[0] for lane in lanes_needed})
    try:
        from auto_rate_builder import build_rate_table_for_customer
        for p in all_pols:
            try:
                result = build_rate_table_for_customer(
                    pol=p, destinations=",".join(all_dests), markup=float(markup or 0)
                )
                # Extract per-lane rates from all_rows (via "rates" field)
                for rate_row in result.get("rates", []):
                    pod = str(rate_row.get("pod_code", "")).upper()
                    r40 = rate_row.get("rate_40")
                    r20 = rate_row.get("rate_20")
                    key = (p, pod)
                    # Keep cheapest carrier per lane
                    if key not in lane_rates or (r40 and r40 < lane_rates[key].get("rate_40", 1e9)):
                        lane_rates[key] = {
                            "rate_20": int(r20) if r20 else 0,
                            "rate_40": int(r40) if r40 else 0,
                            "carrier": str(rate_row.get("carrier", "")),
                            "etd": str(rate_row.get("exp", ""))[:10] if rate_row.get("exp") else "",
                        }
            except Exception as e:
                log.debug(f"[prospects] auto_rate_builder POL={p}: {e}")
    except Exception as e:
        log.warning(f"[prospects] auto_rate_builder unavailable: {e}")

    # Apply rates to prospects
    for p in prospects:
        lane = (p["pol"], p["destination"])
        info = lane_rates.get(lane, {})
        if info.get("rate_40"):
            p["rate_40"] = int(info["rate_40"])
            p["rate_20"] = int(info.get("rate_20", 0))
            if info.get("etd"):
                p["etd"] = str(info["etd"])[:10]

    return {"prospects": prospects, "total": len(prospects)}


class V4BulkSendRequest(BaseModel):
    emails: list
    campaign_id: str = ""
    markup: float = 20.0
    subject: str = ""


@app.post("/api/email-rate/campaign/bulk-send", status_code=202)
def v4_bulk_send(req: V4BulkSendRequest, background_tasks: BackgroundTasks):
    cnee_src = CNEE_V2 if CNEE_V2.exists() else (CNEE_V1 if CNEE_V1.exists() else None)
    if not cnee_src:
        raise HTTPException(404, "cnee_master not found")
    df = pd.read_excel(cnee_src)
    df.columns = df.columns.str.strip().str.upper()
    email_col = "EMAIL" if "EMAIL" in df.columns else "CNEE_EMAIL"
    targets = df[df[email_col].astype(str).str.lower().isin([e.lower() for e in req.emails])]
    contacts = []
    for _, row in targets.iterrows():
        contacts.append(ContactItem(
            email=str(row.get(email_col, "")).strip(),
            pic=str(row.get("CNEE_PIC", "Team")).strip(),
            company=str(row.get("CNEE_NAME", row.get("COMPANY", ""))).strip(),
            pol=str(row.get("POL", "HPH")).strip(),
            dest=str(row.get("DESTINATION", "USLAX,USLGB,USEWR,USSAV")).strip(),
        ))
    if not contacts:
        raise HTTPException(404, "No matching contacts found")
    v2_req = SendRequest(contacts=contacts, subject=req.subject, markup=req.markup)
    campaign_id = f"V4_{datetime.now():%Y%m%d_%H%M%S}"
    SEND_PROGRESS[campaign_id] = {"sent": 0, "total": len(contacts), "errors": [], "status": "queued", "skipped_cooldown": 0}
    background_tasks.add_task(_do_send, campaign_id, v2_req)
    return {"sent": len(contacts), "failed": 0, "campaign_id": campaign_id, "status": "queued"}


@app.get("/api/email-rate/campaign/stats")
def v4_stats():
    return get_history_stats()


@app.get("/api/email-rate/follow-up-queue")
def v4_followup_queue():
    return {"queue": [], "total": 0}


@app.get("/api/email-events/alerts")
def v4_alerts():
    return {"alerts": []}


@app.get("/api/data/email-log")
def v4_email_log(limit: int = 100):
    return get_history(limit=limit)


@app.get("/", response_class=HTMLResponse)
def serve_dashboard():
    # Prefer the v4 dashboard in plans/visuals; fall back to legacy.
    candidates = [
        ENGINE_TEST / "plans" / "visuals" / "email-dashboard-v4.html",
        ENGINE_TEST / "email_dashboard.html",
    ]
    for html in candidates:
        if html.exists():
            return html.read_text(encoding="utf-8")
    return "<h1>Dashboard HTML not found</h1>"


# ============================================================================
# ROUND 2 — BATCH / QUEUE / INTEL / MARKET / SCANNER ENDPOINTS
# ============================================================================
# Wires Round 1 modules (queue_store, intel/*, intelligence/*, scanner/*)
# into the dashboard. Each import is try/except-wrapped so the server still
# boots if one module has issues.

log.info("Initializing Round 2 integration (queue + intel + market + scanner)...")

# ---- Round 1 module imports (graceful) ------------------------------------
_R1 = {"queue": False, "intel": False, "market": False, "scanner": False,
       "builder": False, "writeback": False}
try:
    from email_engine import queue_store as _queue_store  # type: ignore
    _R1["queue"] = True
except Exception as _e:
    log.warning(f"[R2] queue_store import failed: {_e}")
    _queue_store = None  # type: ignore

try:
    from email_engine.intel import memory as _intel_memory  # type: ignore
    _R1["intel"] = True
except Exception as _e:
    log.warning(f"[R2] intel.memory import failed: {_e}")
    _intel_memory = None  # type: ignore

try:
    from email_engine.intelligence import market_engine as _market_engine  # type: ignore
    _R1["market"] = True
except Exception as _e:
    log.warning(f"[R2] market_engine import failed: {_e}")
    _market_engine = None  # type: ignore

try:
    from email_engine.intelligence import builder as _builder  # type: ignore
    _R1["builder"] = True
except Exception as _e:
    log.warning(f"[R2] intelligence.builder import failed: {_e}")
    _builder = None  # type: ignore

try:
    from email_engine.intel import writeback as _writeback  # type: ignore
    _R1["writeback"] = True
except Exception as _e:
    log.warning(f"[R2] intel.writeback import failed: {_e}")
    _writeback = None  # type: ignore

try:
    from email_engine.scanner import inbox_scanner as _scanner  # type: ignore
    _R1["scanner"] = True
except Exception as _e:
    log.warning(f"[R2] scanner import failed: {_e}")
    _scanner = None  # type: ignore


# Resolve CNEE master v2 location (OneDrive primary, local fallback)
def _resolve_cnee_master_v2() -> Path:
    try:
        from shared.paths import EMAIL_DATA  # type: ignore
        p = EMAIL_DATA / "cnee_master_v2.xlsx"
        if p.exists():
            return p
    except Exception:
        pass
    for candidate in [
        Path("D:/OneDrive/NelsonData/email/cnee_master_v2_final.xlsx"),  # 28K full
        Path("D:/OneDrive/NelsonData/email/cnee_master_v2.xlsx"),
        CNEE_V2,
    ]:
        if candidate.exists():
            return candidate
    return CNEE_V2  # last-resort (may not exist yet)


CNEE_MASTER_V2_PATH = _resolve_cnee_master_v2()

# Default destinations used when a CNEE row has no destination column
# 2026-04-17: 9 main lanes (was 5) — covers HPH/HCM→US main port + inland gateways
DEFAULT_DESTINATIONS = ["USLAX", "USLGB", "USSAV", "USNYC", "USORF", "USCHS", "USTIW", "USCHI", "USDAL"]


# ---- Startup hook ----------------------------------------------------------
@app.on_event("startup")
def _r2_startup():
    """Initialize Round 1 DBs + background threads + scheduler."""
    if _queue_store is not None:
        try:
            _queue_store.init_db()
            log.info("[R2] queue_store DB initialized")
        except Exception as e:
            log.warning(f"[R2] queue_store init failed: {e}")

    if _intel_memory is not None:
        try:
            _intel_memory.init_db()
            log.info("[R2] intel.memory DB initialized")
        except Exception as e:
            log.warning(f"[R2] intel.memory init failed: {e}")

    if _writeback is not None:
        try:
            _writeback.start_background_flusher()
            log.info("[R2] writeback flusher started")
        except Exception as e:
            log.warning(f"[R2] writeback flusher failed: {e}")

    if _scanner is not None and os.environ.get("NELSON_DISABLE_SCANNER") != "1":
        try:
            app.state.scheduler = _scanner.start_scheduler()
            log.info("[R2] scanner scheduler started")
        except Exception as e:
            log.warning(f"[R2] scanner scheduler skipped: {e}")
    else:
        app.state.scheduler = None

    log.info(f"[R2] modules ready: {_R1}")


# ============================================================================
# QUEUE ENDPOINTS
# ============================================================================

class BatchEnqueueRequest(BaseModel):
    batch_id: str
    cnee_emails: List[str] = Field(..., min_length=1)
    campaign_id: str = ""
    markup: float = 20.0
    dry_run: bool = False
    pol: str = "HPH"
    destinations: str = ""  # comma/semicolon separated; empty = use row's dest or defaults


def _row_to_profile(row: dict) -> dict:
    """Map a cnee_master_v2 row (dict) to the builder's profile dict."""
    def _s(k: str, default: str = "") -> str:
        v = row.get(k)
        if v is None:
            return default
        s = str(v).strip()
        return default if s.lower() in ("", "nan", "none") else s

    first_name = _s("PIC") or _s("GREETING") or ""
    # Greeting often "Dear John," → strip salutation clutter
    if first_name.lower().startswith("dear "):
        first_name = first_name[5:].rstrip(",.").strip()
    # Guard against garbage: placeholder words, pure digits, address tokens
    _pic_bad_tokens = {"hi","hello","dear","team","sir","madam","mr","mrs","ms","customer","na","n/a","null","none","nan"}
    first_name = _clean_pic(first_name, _s("COMPANY"))

    return {
        "first_name": first_name.split()[0] if first_name else "Team",
        "name": _s("PIC"),
        "company": _s("COMPANY"),
        "tier": _s("TIER"),
        "priority_score": int(float(row.get("PRIORITY_SCORE") or 0)) if str(row.get("PRIORITY_SCORE") or "").replace(".", "").isdigit() else 0,
        "quality_score": row.get("EMAIL_QUALITY_SCORE"),
        "pol": _s("POL"),
        "destination": _s("DESTINATION"),
        "campaign_id": _s("CAMPAIGN_ID"),
        "send_count": row.get("SEND_COUNT"),
        "last_sent_date": _s("LAST_SENT_DATE"),
    }


@app.post("/api/email-rate/batch/enqueue")
def batch_enqueue(req: BatchEnqueueRequest, confirm: Optional[str] = None):
    """Build smart emails for a list of CNEE emails and enqueue them.

    - Respects KILL_SWITCH.flag (503)
    - Requires ?confirm=yes for batches > 500
    - dry_run=True still builds + returns the payload but does NOT persist to DB
    """
    if _queue_store is None:
        raise HTTPException(503, "queue_store module unavailable")

    if _queue_store.kill_switch_active():
        raise HTTPException(503, "Kill switch active — enqueue refused")

    if len(req.cnee_emails) > 500 and (confirm or "").lower() != "yes":
        raise HTTPException(
            400,
            f"Batch size {len(req.cnee_emails)} exceeds 500 — add ?confirm=yes to proceed",
        )

    # Load CNEE master v2
    master_rows: dict[str, dict] = {}
    try:
        df = pd.read_excel(CNEE_MASTER_V2_PATH)
        df.columns = df.columns.str.strip().str.upper()
        if "EMAIL" in df.columns:
            df["_el"] = df["EMAIL"].astype(str).str.lower().str.strip()
            for _, r in df.iterrows():
                em = r["_el"]
                if em and em not in master_rows:
                    master_rows[em] = r.to_dict()
    except Exception as e:
        log.warning(f"[R2] cnee_master_v2 load failed: {e}")

    # Resolve destinations (request override → row's column → defaults)
    requested_dests: List[str] = []
    if req.destinations:
        requested_dests = [
            d.strip().upper() for d in req.destinations.replace(";", ",").split(",")
            if d.strip()
        ]

    emails_out: list[dict] = []
    skipped: list[dict] = []

    for raw_email in req.cnee_emails:
        em = (raw_email or "").strip().lower()
        if not em:
            continue
        if em in EXCLUDED_EMAILS:
            skipped.append({"email": em, "reason": "excluded (active customer / opt-out)"})
            continue
        row = master_rows.get(em) or {"EMAIL": em}
        profile = _row_to_profile(row)

        # Merge intel summary when available
        if _intel_memory is not None:
            try:
                summary = _intel_memory.get_cnee_summary(em)
                if summary:
                    profile["last_sent_at"] = summary.get("last_sent_at")
                    profile["days_since_last"] = summary.get("days_since_last_reply") or ""
                    if summary.get("current_tier") and not profile.get("tier"):
                        profile["tier"] = summary["current_tier"]
            except Exception as e:
                log.debug(f"intel summary failed for {em}: {e}")

        # Destinations: row value > request filter > default
        # Each CNEE has their OWN destination in cnee_master.
        # Only use request dest as fallback when row is empty.
        row_dest = str(row.get("DESTINATION") or "").strip()
        if row_dest:
            dests = [d.strip().upper() for d in row_dest.replace(";", ",").split(",") if d.strip()]
        elif requested_dests:
            dests = requested_dests
        else:
            dests = DEFAULT_DESTINATIONS

        pol = req.pol or str(row.get("POL") or "HPH").strip().upper() or "HPH"

        # Build smart email
        if _builder is None:
            skipped.append({"email": em, "reason": "builder module unavailable"})
            continue
        try:
            built = _builder.build_email(
                cnee_email=em, pol=pol, destinations=dests,
                markup=float(req.markup), profile=profile,
            )
        except Exception as e:
            skipped.append({"email": em, "reason": f"build failed: {e}"})
            continue

        meta = built.get("meta") or {}
        emails_out.append({
            "cnee_email": em,
            "subject": built.get("subject", ""),
            "html_body": built.get("html_body", ""),
            "tier": profile.get("tier") or "",
            "priority_score": int(profile.get("priority_score") or 0),
            "campaign_id": req.campaign_id or profile.get("campaign_id") or "",
            "meta_json": {
                **meta,
                "dry_run": bool(req.dry_run),
                "profile_first_name": profile.get("first_name"),
            },
        })

    if req.dry_run:
        return {
            "batch_id": req.batch_id,
            "queued": 0,
            "dry_run": True,
            "would_queue": len(emails_out),
            "skipped": skipped,
            "preview": emails_out[:3],  # tiny preview so UI can eyeball
        }

    try:
        queued = _queue_store.enqueue_batch(req.batch_id, emails_out)
    except Exception as e:
        log.exception("enqueue_batch failed")
        raise HTTPException(500, f"enqueue failed: {e}")

    return {
        "batch_id": req.batch_id,
        "queued": queued,
        "requested": len(req.cnee_emails),
        "built": len(emails_out),
        "skipped": skipped,
    }


@app.get("/api/email-rate/batch/{batch_id}/status")
def batch_status(batch_id: str):
    if _queue_store is None:
        raise HTTPException(503, "queue_store module unavailable")
    return _queue_store.get_batch_status(batch_id)


@app.get("/api/email-rate/queue/pending")
def queue_pending(worker_id: str = Query(...), limit: int = 1):
    """Pop the next pending job (worker endpoint)."""
    if _queue_store is None:
        raise HTTPException(503, "queue_store module unavailable")
    jobs = []
    for _ in range(max(1, int(limit))):
        j = _queue_store.pop_one(worker_id)
        if j is None:
            break
        jobs.append(j)
    return {"jobs": jobs, "count": len(jobs)}


class MarkFailedRequest(BaseModel):
    error: str = ""


@app.post("/api/email-rate/queue/mark-sent/{job_id}")
def queue_mark_sent(job_id: int):
    if _queue_store is None:
        raise HTTPException(503, "queue_store module unavailable")
    # Lookup the row so we can log a SENT event into intel
    meta = {}
    try:
        import sqlite3
        conn = sqlite3.connect(_queue_store._DB_PATH)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT cnee_email, subject, batch_id, campaign_id, meta_json FROM email_queue WHERE id=?",
            (job_id,),
        ).fetchone()
        conn.close()
        if row:
            meta = dict(row)
    except Exception as e:
        log.debug(f"lookup job {job_id} for intel event failed: {e}")

    _queue_store.mark_sent(job_id)

    if meta and _intel_memory is not None:
        try:
            import json as _json
            m = meta.get("meta_json")
            mdata = _json.loads(m) if m else {}
            _intel_memory.log_event({
                "event_type": "SENT",
                "cnee_email": meta.get("cnee_email"),
                "subject": meta.get("subject"),
                "template_id": mdata.get("template_id"),
                "market_state": mdata.get("dominant_state"),
                "batch_id": meta.get("batch_id"),
                "campaign_id": meta.get("campaign_id"),
            })
        except Exception as e:
            log.debug(f"intel log_event failed: {e}")

    return {"ok": True, "job_id": job_id}


@app.post("/api/email-rate/queue/mark-failed/{job_id}")
def queue_mark_failed(job_id: int, req: MarkFailedRequest):
    if _queue_store is None:
        raise HTTPException(503, "queue_store module unavailable")
    _queue_store.mark_failed(job_id, req.error or "unknown")
    return {"ok": True, "job_id": job_id}


@app.post("/api/email-rate/queue/reset-stuck")
def queue_reset_stuck(minutes: int = 10):
    if _queue_store is None:
        raise HTTPException(503, "queue_store module unavailable")
    n = _queue_store.reset_stuck(int(minutes))
    return {"reset": int(n)}


@app.get("/api/email-rate/queue/kill-status")
def queue_kill_status():
    if _queue_store is None:
        return {"active": False}
    return {"active": _queue_store.kill_switch_active(),
            "flag_path": _queue_store.KILL_SWITCH_PATH}


@app.post("/api/email-rate/queue/kill")
def queue_kill_engage():
    """Activate kill switch — creates the flag file."""
    if _queue_store is None:
        raise HTTPException(503, "queue_store module unavailable")
    try:
        Path(_queue_store.KILL_SWITCH_PATH).parent.mkdir(parents=True, exist_ok=True)
        Path(_queue_store.KILL_SWITCH_PATH).write_text(
            f"engaged_at={datetime.now().isoformat()}\n", encoding="utf-8",
        )
        return {"ok": True, "active": True}
    except Exception as e:
        raise HTTPException(500, f"kill switch write failed: {e}")


@app.post("/api/email-rate/queue/kill-clear")
def queue_kill_clear():
    """Clear kill switch — deletes the flag file."""
    if _queue_store is None:
        raise HTTPException(503, "queue_store module unavailable")
    try:
        p = Path(_queue_store.KILL_SWITCH_PATH)
        if p.exists():
            p.unlink()
        return {"ok": True, "active": False}
    except Exception as e:
        raise HTTPException(500, f"kill switch clear failed: {e}")


# ============================================================================
# INTEL ENDPOINTS
# ============================================================================

@app.get("/api/intel/profile")
def intel_profile(email: str = Query(...)):
    if _intel_memory is None:
        return {}
    try:
        return _intel_memory.get_cnee_summary(email)
    except Exception as e:
        log.warning(f"intel profile error: {e}")
        return {}


@app.get("/api/intel/timeline")
def intel_timeline(email: str = Query(...), limit: int = 20):
    if _intel_memory is None:
        return {"events": []}
    try:
        events = _intel_memory.get_timeline(email, limit=int(limit))
        return {"events": events, "count": len(events)}
    except Exception as e:
        log.warning(f"intel timeline error: {e}")
        return {"events": []}


@app.get("/api/intel/stale")
def intel_stale(days: int = 7, tier: Optional[str] = None):
    if _intel_memory is None:
        return {"stale": [], "count": 0}
    try:
        rows = _intel_memory.get_stale(days=int(days), tier=tier)
        return {"stale": rows, "count": len(rows), "days": int(days)}
    except Exception as e:
        log.warning(f"intel stale error: {e}")
        return {"stale": [], "count": 0, "error": str(e)}


@app.get("/api/intel/recent-replies")
def intel_recent_replies(since_minutes: int = 60, limit: int = 50):
    if _intel_memory is None:
        return {"replies": [], "count": 0}
    try:
        events = _intel_memory.recent_events("REPLY", limit=int(limit))
        cutoff = (datetime.utcnow() - timedelta(minutes=int(since_minutes))) \
            .strftime("%Y-%m-%d %H:%M:%S")
        filtered = [e for e in events if (e.get("timestamp") or "") >= cutoff]
        return {"replies": filtered, "count": len(filtered),
                "since_minutes": int(since_minutes)}
    except Exception as e:
        log.warning(f"intel recent-replies error: {e}")
        return {"replies": [], "count": 0, "error": str(e)}


# ============================================================================
# MARKET INTEL ENDPOINTS
# ============================================================================

@app.get("/api/intelligence/lanes")
def intelligence_lanes(pol: str = "HPH", destinations: Optional[str] = None):
    if _market_engine is None:
        raise HTTPException(503, "market_engine unavailable")
    dests = (
        [d.strip().upper() for d in destinations.replace(";", ",").split(",") if d.strip()]
        if destinations
        else DEFAULT_DESTINATIONS
    )
    out = []
    for dest in dests:
        try:
            out.append(_market_engine.analyze_lane(pol, dest))
        except Exception as e:
            log.debug(f"market analyze_lane {pol}->{dest} failed: {e}")
            out.append({"pol": pol.upper(), "destination": dest,
                        "state": "STABLE", "error": str(e)})
    return {"pol": pol.upper(), "lanes": out, "count": len(out)}


@app.get("/api/intelligence/lane")
def intelligence_lane(pol: str, dest: str):
    if _market_engine is None:
        raise HTTPException(503, "market_engine unavailable")
    return _market_engine.analyze_lane(pol, dest)


# ============================================================================
# SCANNER ENDPOINTS
# ============================================================================

@app.post("/api/scanner/run-now")
def scanner_run_now():
    if _scanner is None:
        raise HTTPException(503, "scanner module unavailable")
    try:
        stats = _scanner.run_scan()
        return {"ok": True, "stats": stats}
    except Exception as e:
        log.warning(f"scanner run_scan failed: {e}")
        return {"ok": False, "error": str(e)}


@app.get("/api/scanner/status")
def scanner_status():
    sched = getattr(app.state, "scheduler", None)
    if sched is None:
        return {"scheduler_running": False, "jobs": []}
    try:
        jobs = []
        for job in sched.get_jobs():
            jobs.append({
                "id": job.id,
                "next_run_at": str(job.next_run_time) if job.next_run_time else None,
                "trigger": str(job.trigger),
            })
        return {
            "scheduler_running": bool(sched.running),
            "jobs": jobs,
            "count": len(jobs),
        }
    except Exception as e:
        return {"scheduler_running": False, "jobs": [], "error": str(e)}


if __name__ == "__main__":
    import uvicorn
    log.info(f"Parquet: {PARQUET_FILE} (exists={PARQUET_FILE.exists()})")
    log.info(f"Contacts: {len(df_contacts)} | Campaigns: {df_contacts['CMD_NAME'].nunique()}")
    print("\n" + "=" * 50)
    print("  EMAIL DASHBOARD v4 — http://localhost:8100")
    print("=" * 50 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=8100, log_level="info")
