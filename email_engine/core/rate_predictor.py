# -*- coding: utf-8 -*-
"""rate_predictor.py — Vietnam→US freight rate prediction (DuckDB + XGBoost)
Model auto-saves to disk after training, auto-loads on import."""
from __future__ import annotations
import logging, math, sys, pickle, json as _json, time as _time
from pathlib import Path
from datetime import datetime
from typing import Optional
import duckdb, numpy as np, pandas as pd

log = logging.getLogger("rate_predictor")
if not log.handlers:
    logging.basicConfig(level=logging.INFO,
        format="%(asctime)s | %(levelname)-5s | %(name)s | %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)])

try:
    from shared.paths import PARQUET_FILE  # type: ignore
except ImportError:
    PARQUET_FILE = Path(__file__).parent.parent.parent / "Pricing_Engine" / "data" / "Cleaned_Master_History.parquet"
    _od = Path("D:/OneDrive/NelsonData/pricing/Cleaned_Master_History.parquet")
    if _od.exists():
        PARQUET_FILE = _od

_MODEL_CACHE: Optional[dict] = None
_MODEL_CACHE_MTIME: float = 0.0
_FEATURES_CACHE: dict = {}  # key: (str(path), frozenset(corridors_keys)) → (df, expires_at, parquet_mtime)
_FEATURES_TTL_SEC = 600  # 10 minutes
CHARGE_FILTER = "Charge_Name IN ('Total Ocean Freight', 'Base Ocean Freight')"
FEATURE_COLS = ["carrier_count","rate_volatility","days_valid_avg","rate_change_1w",
                "rate_change_4w","rolling_mean_4w","rolling_std_4w","fak_scfi_spread",
                "month_sin","month_cos"]
REQUIRED_COLS = ["carrier_count","rate_volatility","days_valid_avg","rate_change_1w",
                 "rolling_mean_4w","rolling_std_4w","month_sin","month_cos"]

# ── Key corridors to train (Nelson's main trade lanes) ──────────
# POD in parquet uses city names / port codes — match with LIKE patterns
KEY_CORRIDORS = {
    # West Coast
    "HCM→LAX/LGB": {"pol": "HCM", "pods": ["LAX%", "LGB%", "LOS ANGELES%", "LONG BEACH%", "LAX-LGB", "LAX/LGB"]},
    "HPH→LAX/LGB": {"pol": "HPH", "pods": ["LAX%", "LGB%", "LOS ANGELES%", "LONG BEACH%", "LAX-LGB", "LAX/LGB"]},
    "HCM→OAK":     {"pol": "HCM", "pods": ["OAKLAND%", "OAK%"]},
    "HCM→SEA/TAC":  {"pol": "HCM", "pods": ["SEATTLE%", "TACOMA%", "SEA%", "TAC%"]},
    "HPH→SEA/TAC":  {"pol": "HPH", "pods": ["SEATTLE%", "TACOMA%", "SEA%", "TAC%"]},
    # East Coast
    "HCM→NYC":     {"pol": "HCM", "pods": ["NEW YORK%", "NYC%", "NEWY%", "USEWR%"]},
    "HPH→NYC":     {"pol": "HPH", "pods": ["NEW YORK%", "NYC%", "NEWY%", "USEWR%"]},
    "HCM→SAV":     {"pol": "HCM", "pods": ["SAVANNAH%", "SAV%", "USSAV%"]},
    "HPH→SAV":     {"pol": "HPH", "pods": ["SAVANNAH%", "SAV%", "USSAV%"]},
    "HCM→CHS":     {"pol": "HCM", "pods": ["CHARLESTON%", "CHS%", "USCHS%"]},
    "HPH→CHS":     {"pol": "HPH", "pods": ["CHARLESTON%", "CHS%", "USCHS%"]},
    "HCM→ORF":     {"pol": "HCM", "pods": ["NORFOLK%", "ORF%"]},
    "HPH→ORF":     {"pol": "HPH", "pods": ["NORFOLK%", "ORF%"]},
    # Gulf
    "HCM→HOU":     {"pol": "HCM", "pods": ["HOUSTON%", "HOU%"]},
    "HPH→HOU":     {"pol": "HPH", "pods": ["HOUSTON%", "HOU%"]},
    "HCM→MIA":     {"pol": "HCM", "pods": ["MIAMI%", "MIA%"]},
    # Inland
    "HCM→CHI":     {"pol": "HCM", "pods": ["CHICAGO%", "CHI%", "USCHI%"]},
    "HPH→CHI":     {"pol": "HPH", "pods": ["CHICAGO%", "CHI%", "USCHI%"]},
    "HCM→DAL":     {"pol": "HCM", "pods": ["DALLAS%", "DAL%"]},
    # Canada
    "HCM→VAN":     {"pol": "HCM", "pods": ["VANCOUVER%", "VAN%", "CAVAN%"]},
    "HPH→VAN":     {"pol": "HPH", "pods": ["VANCOUVER%", "VAN%", "CAVAN%"]},
}


def extract_features(parquet_path: Path | str = PARQUET_FILE, corridors: dict = None) -> pd.DataFrame:
    """Weekly time-series features for KEY corridors only (cached 10 min, invalidates on parquet mtime change)."""
    corridors = corridors or KEY_CORRIDORS
    p = str(parquet_path).replace("\\", "/")
    cache_key = (p, frozenset(corridors.keys()))

    # Check cache
    now = _time.time()
    cached = _FEATURES_CACHE.get(cache_key)
    if cached is not None:
        df_cached, expires_at, cached_mtime = cached
        try:
            current_mtime = Path(parquet_path).stat().st_mtime
        except Exception:
            current_mtime = cached_mtime
        if now < expires_at and current_mtime == cached_mtime:
            return df_cached.copy()

    log.info("Extracting features for %d key corridors from: %s", len(corridors), p)
    con = duckdb.connect()

    all_dfs = []
    for name, spec in corridors.items():
        pol = spec["pol"]
        pod_conditions = " OR ".join([f"UPPER(POD) LIKE '{pod}'" for pod in spec["pods"]])
        query = f"""
        SELECT '{name}' AS corridor,
               date_trunc('week', CAST(Eff AS DATE)) AS week,
               AVG(CASE WHEN Rate_Type='FAK' OR Rate_Type IS NULL THEN Amount END) AS fak_avg,
               AVG(CASE WHEN Rate_Type='SCFI' THEN Amount END) AS scfi_avg,
               AVG(CASE WHEN Rate_Type='FIX' THEN Amount END) AS fix_avg,
               COUNT(DISTINCT CASE WHEN Rate_Type='FAK' OR Rate_Type IS NULL THEN Carrier END) AS carrier_count,
               STDDEV(CASE WHEN Rate_Type='FAK' OR Rate_Type IS NULL THEN Amount END) AS rate_volatility,
               AVG(CAST(Exp AS DATE) - CAST(Eff AS DATE)) AS days_valid_avg,
               MONTH(date_trunc('week', CAST(Eff AS DATE))) AS month_num
        FROM '{p}'
        WHERE {CHARGE_FILTER} AND Amount BETWEEN 1 AND 50000
          AND POL = '{pol}' AND ({pod_conditions})
          AND Container_Type IN ('40HQ','40HC','40HG')
          AND Eff IS NOT NULL
        GROUP BY date_trunc('week', CAST(Eff AS DATE))
        HAVING fak_avg IS NOT NULL
        ORDER BY week
        """
        try:
            cdf = con.execute(query).df()
            if not cdf.empty:
                all_dfs.append(cdf)
        except Exception as e:
            log.warning("Query failed for %s: %s", name, e)

    con.close()
    if not all_dfs:
        log.warning("No data for any key corridor")
        return pd.DataFrame()

    df = pd.concat(all_dfs, ignore_index=True)
    if df.empty:
        log.warning("No data returned — check parquet path and filters")
        return df
    log.info("Raw weekly rows: %d  corridors: %d", len(df), df["corridor"].nunique())
    df = df.sort_values(["corridor","week"]).reset_index(drop=True)
    df["fak_scfi_spread"] = np.where(
        df["scfi_avg"].notna() & (df["scfi_avg"] > 0),
        (df["fak_avg"] - df["scfi_avg"]) / df["scfi_avg"] * 100, np.nan)
    g = df.groupby("corridor")["fak_avg"]
    df["rate_change_1w"]  = g.pct_change(1) * 100
    df["rate_change_4w"]  = g.pct_change(4) * 100
    df["rolling_mean_4w"] = g.transform(lambda x: x.rolling(4, min_periods=2).mean())
    df["rolling_std_4w"]  = g.transform(lambda x: x.rolling(4, min_periods=2).std())
    df["month_sin"] = np.sin(2 * math.pi * df["month_num"] / 12)
    df["month_cos"] = np.cos(2 * math.pi * df["month_num"] / 12)
    df["rate_volatility"] = df["rate_volatility"].fillna(0)
    df["days_valid_avg"]  = df["days_valid_avg"].fillna(14)
    log.info("Features ready: %d rows, %d corridors", len(df), df["corridor"].nunique())

    # Store in cache
    try:
        new_mtime = Path(parquet_path).stat().st_mtime
    except Exception:
        new_mtime = 0.0
    _FEATURES_CACHE[cache_key] = (df, now + _FEATURES_TTL_SEC, new_mtime)
    return df.copy()


def train_model(features_df: pd.DataFrame) -> dict:
    """Walk-Forward Validation: train expanding window, predict next week, repeat.
    Each iteration learns from all prior data → final benchmark = true OOS performance."""
    try:
        from xgboost import XGBClassifier, XGBRegressor
        from sklearn.metrics import accuracy_score, f1_score
        from sklearn.preprocessing import LabelEncoder
    except ImportError:
        raise ImportError("Run: pip install xgboost scikit-learn")

    df = features_df.sort_values(["corridor","week"]).copy()
    df["next_fak"]    = df.groupby("corridor")["fak_avg"].shift(-1)
    df["target_pct"]  = (df["next_fak"] - df["fak_avg"]) / df["fak_avg"] * 100
    df["direction"]   = df["target_pct"].apply(
        lambda p: None if pd.isna(p) else ("UP" if p > 2 else "DOWN" if p < -2 else "STABLE"))
    df = df.dropna(subset=["direction","target_pct"] + REQUIRED_COLS)
    df[FEATURE_COLS] = df[FEATURE_COLS].fillna(0)

    if len(df) < 50:
        log.warning("Too few training rows: %d", len(df))
        return {}

    df = df.sort_values("week").reset_index(drop=True)
    weeks = sorted(df["week"].unique())
    MIN_TRAIN = min(20, len(weeks) // 2)
    xgb_params = dict(n_estimators=150, max_depth=4, learning_rate=0.05,
                      subsample=0.8, colsample_bytree=0.8, verbosity=0, random_state=42)
    le = LabelEncoder()
    le.fit(df["direction"])

    # Walk-forward: expand training window each week
    wf_results = []
    log.info("Walk-forward: %d weeks, starting from week %d", len(weeks), MIN_TRAIN)
    for i in range(MIN_TRAIN, len(weeks) - 1):
        train_wks = set(weeks[:i])
        test_wk = weeks[i]
        tr = df["week"].isin(train_wks)
        te = df["week"] == test_wk
        if te.sum() == 0 or tr.sum() < 30:
            continue
        X_tr, X_te = df.loc[tr, FEATURE_COLS], df.loc[te, FEATURE_COLS]
        y_dir_tr = le.transform(df.loc[tr, "direction"])
        y_dir_te = le.transform(df.loc[te, "direction"])
        y_mag_tr = df.loc[tr, "target_pct"]
        y_mag_te = df.loc[te, "target_pct"]

        clf = XGBClassifier(**xgb_params, eval_metric="mlogloss", use_label_encoder=False)
        clf.fit(X_tr, y_dir_tr, verbose=False)
        pred_dir = clf.predict(X_te)
        reg = XGBRegressor(**xgb_params)
        reg.fit(X_tr, y_mag_tr)
        pred_mag = reg.predict(X_te)

        for j, (pd_d, pd_m, at_d, at_m) in enumerate(zip(pred_dir, pred_mag, y_dir_te, y_mag_te)):
            wf_results.append({"week": str(test_wk)[:10], "predicted": le.inverse_transform([pd_d])[0],
                "actual": le.inverse_transform([at_d])[0], "pred_pct": round(float(pd_m), 2),
                "actual_pct": round(float(at_m), 2), "correct": int(pd_d) == int(at_d)})

    if not wf_results:
        log.warning("Walk-forward produced no results")
        return {}

    # Calculate walk-forward metrics
    wf_df = pd.DataFrame(wf_results)
    n_correct = wf_df["correct"].sum()
    n_total = len(wf_df)
    ud_mask = wf_df["actual"].isin(["UP", "DOWN"])
    dir_correct = wf_df.loc[ud_mask, "correct"].sum() if ud_mask.sum() > 0 else 0
    dir_total = ud_mask.sum()
    denom = np.abs(wf_df["pred_pct"]) + np.abs(wf_df["actual_pct"]) + 1e-6
    smape = np.mean(2 * np.abs(wf_df["pred_pct"] - wf_df["actual_pct"]) / denom) * 100

    # Train FINAL model on ALL data for production use
    X_all = df[FEATURE_COLS]
    y_dir_all = le.transform(df["direction"])
    y_mag_all = df["target_pct"]
    final_clf = XGBClassifier(**xgb_params, eval_metric="mlogloss", use_label_encoder=False)
    final_clf.fit(X_all, y_dir_all, verbose=False)
    final_reg = XGBRegressor(**xgb_params)
    final_reg.fit(X_all, y_mag_all)

    metrics = {"accuracy": round(n_correct / n_total, 4),
               "f1": round(f1_score(le.transform(wf_df["actual"]), le.transform(wf_df["predicted"]), average="weighted"), 4),
               "mape": round(float(smape), 2),
               "directional_accuracy": round(dir_correct / dir_total, 4) if dir_total > 0 else 0,
               "n_predictions": n_total, "n_walk_forward_weeks": len(weeks) - MIN_TRAIN}
    log.info("Walk-Forward Metrics: %s", metrics)
    fi = dict(zip(FEATURE_COLS, final_clf.feature_importances_))
    last_12 = wf_df.tail(12).to_dict(orient="records")
    return {"model_direction": final_clf, "model_magnitude": final_reg, "label_encoder": le,
            "metrics": metrics, "feature_importance": sorted(fi, key=fi.get, reverse=True)[:10],
            "walk_forward_results": last_12}


def predict(model_dict: dict, current_features: "pd.Series | dict") -> dict:
    """Predict next-week direction and magnitude for a corridor."""
    if not model_dict:
        return {"error": "Model not trained"}
    clf, reg, le = model_dict["model_direction"], model_dict["model_magnitude"], model_dict["label_encoder"]
    if isinstance(current_features, dict):
        current_features = pd.Series(current_features)
    X = pd.DataFrame([pd.to_numeric(current_features[FEATURE_COLS], errors="coerce").fillna(0)])
    proba = clf.predict_proba(X)[0]
    dir_idx = int(np.argmax(proba))
    direction = le.inverse_transform([dir_idx])[0]
    magnitude = float(reg.predict(X)[0])
    spread = current_features.get("fak_scfi_spread", np.nan)
    if pd.notna(spread) and spread == spread:
        if   spread > 70: sig = f"FAK significantly above SCFI ({spread:.1f}%) — market likely to correct downward"
        elif spread > 40: sig = f"FAK moderately above SCFI ({spread:.1f}%) — watch for softening"
        elif spread < 10: sig = f"FAK near SCFI parity ({spread:.1f}%) — market balanced"
        else:             sig = f"FAK-SCFI spread {spread:.1f}% — normal range"
    else:
        sig = "No SCFI benchmark available for this corridor"
    return {"direction": direction, "confidence": round(float(proba[dir_idx]), 4),
            "predicted_change_pct": round(magnitude, 2),
            "fak_scfi_spread": round(float(spread), 2) if pd.notna(spread) and spread == spread else None,
            "signal": sig,
            "top_factors": model_dict.get("feature_importance", FEATURE_COLS)[:3]}


def benchmark(metrics: dict) -> dict:
    """Grade model metrics against industry benchmarks (Xeneta: 70% dir acc, TFT: 10-15% MAPE)."""
    def gda(v): return "A" if v >= 0.70 else "B" if v >= 0.60 else "C"
    def gmp(v): return "A" if v < 10 else "B" if v < 15 else "C" if v < 20 else "D"
    def gf1(v): return "A" if v >= 0.65 else "B" if v >= 0.60 else "C"
    gs = {"directional_accuracy": {"value": metrics.get("directional_accuracy",0), "benchmark": 0.65, "grade": gda(metrics.get("directional_accuracy",0))},
          "mape":      {"value": metrics.get("mape",99),  "benchmark": 15.0, "grade": gmp(metrics.get("mape",99))},
          "f1_score":  {"value": metrics.get("f1",0),     "benchmark": 0.60, "grade": gf1(metrics.get("f1",0))}}
    gv = {"A":4,"B":3,"C":2,"D":1}
    avg = sum(gv[g["grade"]] for g in gs.values()) / len(gs)
    gs["overall_grade"] = "A" if avg>=3.7 else "A-" if avg>=3.3 else "B+" if avg>=3.0 else "B" if avg>=2.7 else "C"
    return gs


def get_market_snapshot(parquet_path: Path | str = PARQUET_FILE) -> dict:
    """Quick market state: current + prev week FAK/SCFI/FIX for HCM/HPH → US 40HQ."""
    p = str(parquet_path)
    log.info("Market snapshot from: %s", p)
    con = duckdb.connect()
    rows = con.execute(f"""
    WITH w AS (
        SELECT date_trunc('week', CAST(Eff AS DATE)) AS week,
               Rate_Type, AVG(Amount) AS avg_rate,
               COUNT(DISTINCT Carrier) AS carriers
        FROM '{p}'
        WHERE POL IN ('HCM','HPH') AND Container_Type='40HQ'
          AND {CHARGE_FILTER} AND Amount BETWEEN 1 AND 50000
          AND Rate_Type IN ('FAK','SCFI','FIX')
        GROUP BY week, Rate_Type
    )
    SELECT * FROM w WHERE week >= (SELECT MAX(week) FROM w) - INTERVAL '14 days'
    ORDER BY week DESC, Rate_Type
    """).fetchall()
    con.close()

    from collections import defaultdict
    bw: dict = defaultdict(dict)
    for week, rt, avg, carriers in rows:
        bw[str(week)[:10]][rt] = {"avg": round(avg, 0), "carriers": carriers}
    wks = sorted(bw.keys(), reverse=True)
    if not wks:
        return {"error": "No data found for HCM/HPH 40HQ"}
    cur, prev = bw[wks[0]], bw[wks[1]] if len(wks) > 1 else {}
    fak_now, scfi_now = cur.get("FAK",{}).get("avg"), cur.get("SCFI",{}).get("avg")
    fak_prev = prev.get("FAK",{}).get("avg")
    spread = round((fak_now-scfi_now)/scfi_now*100, 1) if fak_now and scfi_now else None
    trend = None
    if fak_now and fak_prev:
        d = (fak_now - fak_prev) / fak_prev * 100
        trend = "UP" if d > 1 else "DOWN" if d < -1 else "FLAT"
    return {"current_week": wks[0], "previous_week": wks[1] if len(wks)>1 else None,
            "fak_avg": fak_now, "scfi_avg": scfi_now,
            "fix_avg": cur.get("FIX",{}).get("avg"),
            "fak_scfi_spread_pct": spread, "active_carriers": cur.get("FAK",{}).get("carriers"),
            "trend_vs_last_week": trend, "previous_fak": fak_prev}


# ── Model persistence ──────────────────────────────────────────
MODEL_DIR = Path(__file__).parent.parent / "models"
MODEL_DIR.mkdir(exist_ok=True)
MODEL_FILE = MODEL_DIR / "rate_model.pkl"
META_FILE = MODEL_DIR / "rate_model_meta.json"


def save_model(model_dict: dict) -> None:
    """Save trained model to disk for persistence across restarts."""
    try:
        # Save XGBoost models + label encoder
        with open(MODEL_FILE, "wb") as f:
            pickle.dump({
                "model_direction": model_dict["model_direction"],
                "model_magnitude": model_dict["model_magnitude"],
                "label_encoder": model_dict["label_encoder"],
                "feature_importance": model_dict.get("feature_importance", []),
            }, f)
        # Save metadata as JSON
        meta = {
            "trained_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "metrics": model_dict.get("metrics", {}),
            "walk_forward_results": model_dict.get("walk_forward_results", []),
            "corridors": list(KEY_CORRIDORS.keys()),
        }
        META_FILE.write_text(_json.dumps(meta, indent=2, default=str), encoding="utf-8")
        log.info("Model saved to %s (trained: %s)", MODEL_FILE, meta["trained_at"])
    except Exception as e:
        log.error("Failed to save model: %s", e)


def load_model() -> Optional[dict]:
    """Load saved model from disk (cached per process; invalidates on file mtime change)."""
    global _MODEL_CACHE, _MODEL_CACHE_MTIME
    if not MODEL_FILE.exists():
        return None
    try:
        current_mtime = MODEL_FILE.stat().st_mtime
        if _MODEL_CACHE is not None and current_mtime == _MODEL_CACHE_MTIME:
            return _MODEL_CACHE
        with open(MODEL_FILE, "rb") as f:
            model = pickle.load(f)
        meta = {}
        if META_FILE.exists():
            meta = _json.loads(META_FILE.read_text(encoding="utf-8"))
        model["metrics"] = meta.get("metrics", {})
        model["walk_forward_results"] = meta.get("walk_forward_results", [])
        model["trained_at"] = meta.get("trained_at", "unknown")
        log.info("Model loaded from disk (trained: %s)", model["trained_at"])
        _MODEL_CACHE = model
        _MODEL_CACHE_MTIME = current_mtime
        return model
    except Exception as e:
        log.warning("Failed to load model: %s", e)
        return None


def get_model_status() -> dict:
    """Check if model exists on disk and when it was trained."""
    if META_FILE.exists():
        meta = _json.loads(META_FILE.read_text(encoding="utf-8"))
        return {"trained": True, "trained_at": meta.get("trained_at"),
                "metrics": meta.get("metrics", {}), "corridors": len(meta.get("corridors", []))}
    return {"trained": False}


if __name__ == "__main__":
    import json
    print("=" * 60)
    snap = get_market_snapshot()
    print("[Market Snapshot]"); print(json.dumps(snap, indent=2, default=str))
    print("\n[Extracting features...]")
    df = extract_features()
    if df.empty: sys.exit(1)
    print(f"Features: {len(df)} rows, {df['corridor'].nunique()} corridors")
    print("\n[Training...]")
    model = train_model(df)
    if not model: sys.exit(1)
    save_model(model)
    print("Metrics:", json.dumps(model["metrics"], indent=2))
    print("\n[Benchmark]")
    print(json.dumps(benchmark(model["metrics"]), indent=2))
    print("[DONE]")
