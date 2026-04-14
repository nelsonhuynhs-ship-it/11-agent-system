# web_server.py — Email Dashboard Server v2
import sys, csv, random, logging
from pathlib import Path
from datetime import date, datetime
from typing import List

BASE_DIR = Path(__file__).parent
ENGINE_TEST = BASE_DIR.parent
sys.path.insert(0, str(ENGINE_TEST))
sys.path.insert(0, str(BASE_DIR / "core"))

import pandas as pd
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("email-dash")

try:
    from shared.paths import PARQUET_FILE
except ImportError:
    PARQUET_FILE = ENGINE_TEST / "Pricing_Engine" / "data" / "Cleaned_Master_History.parquet"

DATA_FILE   = BASE_DIR / "data.xlsx"
CONFIG_FILE = BASE_DIR / "data" / "config.xlsx"
LOG_FILE    = BASE_DIR / "logs" / "email_log.csv"
CNEE_V2     = BASE_DIR / "data" / "cnee_master_v2.xlsx"
CNEE_V1     = BASE_DIR / "data" / "cnee_master.xlsx"
(BASE_DIR / "logs").mkdir(exist_ok=True)

SEND_PROGRESS: dict = {}  # campaign_id → {sent, total, errors, status}

log.info("Loading data.xlsx...")
df_contacts = pd.read_excel(DATA_FILE)
df_contacts.columns = df_contacts.columns.str.strip().str.upper()
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
    contacts: List[ContactItem] = Field(..., min_length=1, max_length=50)
    subject: str = ""
    default_pol: str = "HPH"
    default_dest: str = "USLAX,USLGB,USEWR,USSAV,USCHI"
    markup: float = Field(default=20.0, ge=0, le=500)
    arb_origin: str = ""  # Optional cross-origin key (e.g. "shanghai")

def err(code: int, msg: str):
    raise HTTPException(status_code=code, detail={"error": msg})

app = FastAPI(title="Email Dashboard v2")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8230", "http://localhost:8231", "http://localhost:3000", "http://127.0.0.1:8230", "http://127.0.0.1:8231"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

@app.get("/api/campaigns")
def get_campaigns():
    cmds = df_contacts.groupby("CMD_NAME").size().reset_index(name="count")
    cmds = cmds.sort_values("count", ascending=False)
    return [{"name": r["CMD_NAME"], "count": int(r["count"])} for _, r in cmds.iterrows()]

@app.get("/api/contacts")
def get_contacts(campaign: str):
    subset = df_contacts[df_contacts["CMD_NAME"] == campaign].copy()
    subset = subset[subset["CNEE_EMAIL"].notna()]
    subset["_el"] = subset["CNEE_EMAIL"].astype(str).str.lower().str.strip()
    subset = subset.drop_duplicates(subset="_el")

    results = []
    for _, row in subset.iterrows():
        def clean(field, default=""):
            v = str(row.get(field, "")).strip()
            return default if v.lower() in ("nan", "") else v
        results.append({
            "email": clean("CNEE_EMAIL"), "pic": clean("CNEE_PIC", "Team"),
            "company": clean("CNEE_NAME"), "pol": clean("POL"), "dest": clean("DESTINATION"),
        })
    results.sort(key=lambda x: x["company"])
    return {"contacts": results, "subject": gen_subject(), "total": len(results)}

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
        # Suppression check: skip hard bounced / invalid / no-MX emails
        if c.email.strip().lower() in suppressed_emails and not c.force_send:
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
            pol  = c.pol or req.default_pol
            dest = c.dest or req.default_dest
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
            m = outlook.CreateItem(0)
            m.To = c.email
            m.Subject = subj
            body = f"<p>Dear {c.pic},</p><p>{intro}</p>{html}<br><p>{closing}</p>"
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

@app.get("/api/whatsapp/log")
def wa_log_endpoint(limit: int = 100):
    wa_log_path = BASE_DIR / "logs" / "whatsapp_log.csv"
    if not wa_log_path.exists():
        return []
    df = pd.read_csv(wa_log_path)
    return df.sort_values("timestamp", ascending=False).head(limit).to_dict(orient="records")


@app.get("/", response_class=HTMLResponse)
def serve_dashboard():
    html = ENGINE_TEST / "email_dashboard.html"
    return html.read_text(encoding="utf-8") if html.exists() else "<h1>Dashboard HTML not found</h1>"

if __name__ == "__main__":
    import uvicorn
    log.info(f"Parquet: {PARQUET_FILE} (exists={PARQUET_FILE.exists()})")
    log.info(f"Contacts: {len(df_contacts)} | Campaigns: {df_contacts['CMD_NAME'].nunique()}")
    print("\n" + "=" * 50)
    print("  EMAIL DASHBOARD v2 — http://localhost:8231")
    print("=" * 50 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=8231, log_level="info")
