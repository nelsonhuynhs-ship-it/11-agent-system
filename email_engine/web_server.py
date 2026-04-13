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
def rate_preview(pol: str, destinations: str, markup: float = 20.0):
    from auto_rate_builder import build_rate_table_for_customer
    try:
        return build_rate_table_for_customer(pol=pol, destinations=destinations, markup=markup)
    except Exception as e:
        log.warning(f"Rate preview failed: {e}")
        return {"routes_found": 0, "total_rates": 0, "html": "", "routes_detail": []}

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

    intro     = CFG.get("INTROTEXT", CFG.get("IntroText", ""))
    closing   = CFG.get("CLOSINGTEXT", CFG.get("ClosingText", ""))
    signature = CFG.get("SIGNATURE", CFG.get("Signature", ""))
    cooldown_map = _load_cooldown_map()
    cutoff = datetime.now() - pd.Timedelta(hours=48)

    for c in req.contacts:
        # Cooldown check: skip if sent within last 48 hours
        last_sent = cooldown_map.get(c.email.strip().lower())
        if last_sent and last_sent > cutoff and not c.force_send:
            prog["skipped_cooldown"] = prog.get("skipped_cooldown", 0) + 1
            log.info(f"COOLDOWN -> {c.email} (last: {last_sent})")
            continue
        try:
            pol  = c.pol or req.default_pol
            dest = c.dest or req.default_dest
            result = build_rate_table_for_customer(pol=pol, destinations=dest, markup=req.markup)
            html = result.get("html", "")
            if not html and not c.force_send:
                prog["skipped"] = prog.get("skipped", 0) + 1
                continue
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
