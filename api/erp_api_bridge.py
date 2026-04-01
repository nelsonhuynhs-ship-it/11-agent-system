# -*- coding: utf-8 -*-
"""
erp_api_bridge.py — Python CLI Bridge for Excel VBA
======================================================
Called by Excel VBA via Shell() to interact with the Nelson Freight API.

Usage from VBA:
    Shell "python erp_api_bridge.py refresh --pol HPH --container 40HQ"
    Shell "python erp_api_bridge.py create_quote --customer HML --carrier CMA ..."
    Shell "python erp_api_bridge.py check_status --customer HML"

Usage from PowerShell (testing):
    python erp_api_bridge.py refresh --pol HPH --container 40HQ
    python erp_api_bridge.py create_quote --customer HML --carrier CMA --place Denver
    python erp_api_bridge.py check_status --customer HML
"""

import argparse
import json
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("erp_bridge")

# ── Config ────────────────────────────────────────────────────────────────────
API_URL = os.environ.get("NELSON_API_URL", "http://localhost:8000")
API_KEY = os.environ.get("NELSON_API_KEY", "")


def _api_call(method: str, path: str, params: dict = None, json_data: dict = None):
    """Make API call with optional API key."""
    try:
        import httpx
    except ImportError:
        import urllib.request
        import urllib.parse
        url = f"{API_URL}{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url)
        if API_KEY:
            req.add_header("X-API-Key", API_KEY)
        if json_data:
            req.add_header("Content-Type", "application/json")
            req.method = "POST"
            req.data = json.dumps(json_data).encode("utf-8")
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))

    # httpx version (preferred)
    headers = {}
    if API_KEY:
        headers["X-API-Key"] = API_KEY

    with httpx.Client(base_url=API_URL, timeout=30) as client:
        if method.upper() == "GET":
            resp = client.get(path, params=params, headers=headers)
        elif method.upper() == "POST":
            resp = client.post(path, json=json_data, headers=headers)
        else:
            raise ValueError(f"Unsupported method: {method}")

        resp.raise_for_status()
        return resp.json()


# ══════════════════════════════════════════════════════════════════════════════
# COMMANDS
# ══════════════════════════════════════════════════════════════════════════════

def cmd_refresh(args):
    """Pull rate matrix for Excel refresh."""
    log.info("Fetching rate matrix (POL=%s, container=%s, mode=%s)...",
             args.pol, args.container, args.mode)

    data = _api_call("GET", "/api/erp/rates-matrix", params={
        "pol": args.pol,
        "container": args.container or "ALL",
        "mode": args.mode,
    })

    summary = data.get("summary", {})
    rows = data.get("rows", [])
    log.info("Got %d rates from %d carriers across %d places",
             summary.get("total_rates", 0),
             summary.get("carrier_count", 0),
             summary.get("place_count", 0))

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        log.info("Saved to %s", args.output)
    else:
        # Print summary for VBA to parse
        print(json.dumps({
            "success": True,
            "total_rates": len(rows),
            "carriers": summary.get("carriers", []),
            "places": summary.get("places", [])[:10],
        }))

    return data


def cmd_create_quote(args):
    """Create a quote via API."""
    log.info("Creating quote: %s → %s (carrier: %s)...",
             args.customer, args.place, args.carrier)

    payload = {
        "customer": args.customer,
        "pol": args.pol,
        "place": args.place,
        "carrier": args.carrier,
        "container_type": args.container,
        "ocean_freight": args.ocean_freight,
        "markup": args.markup,
        "sell_rate": args.sell_rate,
        "transit": args.transit or "",
        "freetime": args.freetime or "",
        "validity": args.validity or "",
    }

    result = _api_call("POST", "/api/erp/sync-quote", json_data=payload)
    log.info("Quote created: %s", result.get("quote_id", "?"))
    print(json.dumps(result))
    return result


def cmd_check_status(args):
    """Check job/shipment status."""
    params = {}
    if args.customer:
        params["customer"] = args.customer
    if args.shipment_id:
        params["shipment_id"] = args.shipment_id
    if args.quote_id:
        params["quote_id"] = args.quote_id

    log.info("Checking status (filter: %s)...", params)
    data = _api_call("GET", "/api/erp/job-status", params=params)

    jobs = data.get("jobs", [])
    log.info("Found %d jobs", len(jobs))

    for job in jobs[:5]:
        log.info("  %s | %s | %s → %s | $%.0f | %s",
                 job["id"], job["customer"], job["carrier"],
                 job["routing"], job.get("selling_rate", 0), job["stage"])

    print(json.dumps(data))
    return data


def cmd_cost_breakdown(args):
    """Get cost breakdown for Excel."""
    log.info("Cost breakdown: %s → %s (carrier: %s, %s)...",
             args.pol, args.place, args.carrier, args.container)

    data = _api_call("GET", "/api/erp/cost-breakdown", params={
        "pol": args.pol,
        "place": args.place,
        "carrier": args.carrier,
        "container": args.container,
    })

    charges = data.get("charges", [])
    log.info("Total: $%.0f (%d charges)", data.get("total", 0), len(charges))
    for c in charges:
        log.info("  %-30s $%.0f", c["charge_name"], c["amount"])

    print(json.dumps(data))
    return data


# ══════════════════════════════════════════════════════════════════════════════
# CLI PARSER
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Nelson Freight ERP ↔ API Bridge",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python erp_api_bridge.py refresh --pol HPH --container 40HQ
  python erp_api_bridge.py create_quote --customer HML --carrier CMA --place Denver --ocean_freight 1450 --markup 150
  python erp_api_bridge.py check_status --customer HML
  python erp_api_bridge.py cost_breakdown --place Denver --carrier CMA
""",
    )
    sub = parser.add_subparsers(dest="command", help="Command to run")

    # refresh
    p_refresh = sub.add_parser("refresh", help="Pull rate matrix for Excel")
    p_refresh.add_argument("--pol", default="HPH")
    p_refresh.add_argument("--container", default=None)
    p_refresh.add_argument("--mode", default="DRY")
    p_refresh.add_argument("--output", default=None, help="Output JSON file path")

    # create_quote
    p_quote = sub.add_parser("create_quote", help="Create quote via API")
    p_quote.add_argument("--customer", required=True)
    p_quote.add_argument("--pol", default="HPH")
    p_quote.add_argument("--place", required=True)
    p_quote.add_argument("--carrier", required=True)
    p_quote.add_argument("--container", default="40HQ")
    p_quote.add_argument("--ocean_freight", type=float, default=0)
    p_quote.add_argument("--markup", type=float, default=0)
    p_quote.add_argument("--sell_rate", type=float, default=0)
    p_quote.add_argument("--transit", default="")
    p_quote.add_argument("--freetime", default="")
    p_quote.add_argument("--validity", default="")

    # check_status
    p_status = sub.add_parser("check_status", help="Check job/shipment status")
    p_status.add_argument("--customer", default=None)
    p_status.add_argument("--shipment_id", default=None)
    p_status.add_argument("--quote_id", default=None)

    # cost_breakdown
    p_cost = sub.add_parser("cost_breakdown", help="Get cost breakdown")
    p_cost.add_argument("--pol", default="HPH")
    p_cost.add_argument("--place", required=True)
    p_cost.add_argument("--carrier", required=True)
    p_cost.add_argument("--container", default="40HQ")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    commands = {
        "refresh": cmd_refresh,
        "create_quote": cmd_create_quote,
        "check_status": cmd_check_status,
        "cost_breakdown": cmd_cost_breakdown,
    }

    try:
        commands[args.command](args)
    except Exception as e:
        log.error("ERROR: %s", e)
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
