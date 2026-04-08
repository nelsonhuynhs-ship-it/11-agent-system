"""
Fox Spirit Tool: Query forecast predictions for a specific route.
Usage: python forecast-query.py USLAX 40HQ
       python forecast-query.py "NEW YORK"
       python forecast-query.py --summary
"""
import sys
import os
import json

# Add forecast dir to path
FORECAST_DIR = "D:/OneDrive/NelsonData/pricing/forecast"
sys.path.insert(0, FORECAST_DIR)
import config as cfg

# POD normalization (same as query-rate.py)
POD_MAP = {
    "USLAX": "LAX", "LAX": "LAX", "LGB": "LAX", "LONGBEACH": "LAX",
    "USNYC": "NEW YORK", "NYC": "NEW YORK", "NEWYORK": "NEW YORK",
    "USSEA": "SEATTLE", "SEA": "SEATTLE", "SEATTLE": "SEATTLE",
    "CAVNC": "VANCOUVER", "VAN": "VANCOUVER", "VANCOUVER": "VANCOUVER",
    "USHOU": "HOUSTON", "HOU": "HOUSTON", "HOUSTON": "HOUSTON",
    "USMIA": "MIAMI", "MIA": "MIAMI", "MIAMI": "MIAMI",
}


def normalize_pod(raw):
    return POD_MAP.get(raw.upper().replace(" ", ""), raw.upper())


def load_latest_forecast():
    if not os.path.exists(cfg.FORECAST_MEMORY_PATH):
        return None, None
    with open(cfg.FORECAST_MEMORY_PATH, "r") as f:
        memory = json.load(f)
    if not memory:
        return None, None
    latest_week = sorted(memory.keys())[-1]
    return memory[latest_week], latest_week


def query_route(pod, container="40HQ"):
    predictions, week = load_latest_forecast()
    if not predictions:
        print(json.dumps({"error": "No forecast data found"}))
        return

    region = normalize_pod(pod)
    results = []
    for key, pred in predictions.items():
        parts = key.split("|")
        if len(parts) != 4:
            continue
        carrier, reg, rate_type, cont = parts
        if reg != region or rate_type != "FAK" or cont != container:
            continue
        results.append({
            "carrier": carrier,
            "region": region,
            "last_price": pred.get("last_price", 0),
            "forecast_mid": pred.get("predicted_mid", 0),
            "forecast_low": pred.get("predicted_low", 0),
            "forecast_high": pred.get("predicted_high", 0),
            "direction": pred.get("predicted_direction", "FLAT"),
            "regime": pred.get("regime", "UNKNOWN"),
            "change_pct": pred.get("pct_change", 0),
        })

    results.sort(key=lambda x: x["last_price"])
    output = {
        "week": week,
        "query": f"{region} {container}",
        "n_carriers": len(results),
        "carriers": results,
    }

    # Add recommendation
    if results:
        cheapest = results[0]
        output["recommendation"] = (
            f"Re nhat: {cheapest['carrier']} ${cheapest['last_price']:,} "
            f"(du bao: ${cheapest['forecast_low']:,}-${cheapest['forecast_high']:,})"
        )

    print(json.dumps(output, ensure_ascii=False, indent=2))


def summary():
    predictions, week = load_latest_forecast()
    if not predictions:
        print(json.dumps({"error": "No forecast data"}))
        return

    # Count by direction (FAK 40HQ only)
    up = down = flat = 0
    opportunities = []
    warnings = []
    for key, pred in predictions.items():
        parts = key.split("|")
        if len(parts) != 4:
            continue
        carrier, region, rate_type, container = parts
        if container != "40HQ" or rate_type != "FAK":
            continue
        d = pred.get("predicted_direction", "FLAT")
        if d == "UP": up += 1
        elif d == "DOWN": down += 1
        else: flat += 1

        if pred.get("regime") == "BOTTOM" and d == "UP":
            opportunities.append(f"{carrier}->{region} ${pred.get('last_price',0):,} BOTTOM+UP")
        if pred.get("pct_change", 0) > 5:
            warnings.append(f"{carrier}->{region} +{pred.get('pct_change',0)}%")

    output = {
        "week": week,
        "total": up + down + flat,
        "up": up, "down": down, "flat": flat,
        "opportunities": opportunities[:5],
        "warnings": warnings[:5],
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or "--summary" in args:
        summary()
    else:
        pod = args[0]
        container = args[1] if len(args) > 1 else "40HQ"
        query_route(pod, container)
