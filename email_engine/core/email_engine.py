import pandas as pd
import yaml
import re
from datetime import datetime


SHIPMENT_FILE = "shipment.xlsx"
SHIPMENT_SHEET = "DEC 2025"
RULES_FILE = "rules.yaml"
FOLDER_MAP_FILE = "folder_map.yaml"


# =========================
# NORMALIZER
# =========================
class ShipmentNormalizer:

    @staticmethod
    def customer(v):
        return str(v).strip().upper() if pd.notna(v) else ""

    @staticmethod
    def routing(v):
        if not v or pd.isna(v):
            return ""
        v = str(v).upper().strip()
        v = re.sub(r"\s+VIA\s+.*$", "", v)
        v = re.sub(r"\s+", "", v)
        return v

    @staticmethod
    def bkg(v):
        if not v or pd.isna(v):
            return ""
        return re.sub(r"[^A-Z0-9]", "", str(v).upper())

    @staticmethod
    def in_time_window(row, ref_date):
        etd = pd.to_datetime(row.get("ETD"), errors="coerce")
        eta = pd.to_datetime(row.get("ETA"), errors="coerce")

        if pd.isna(etd) and pd.isna(eta):
            return True

        for d in [etd, eta]:
            if pd.notna(d):
                diff = abs((d.year - ref_date.year) * 12 + (d.month - ref_date.month))
                if diff <= 1:
                    return True
        return False


# =========================
# LOADERS
# =========================
def load_rules():
    with open(RULES_FILE, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_folder_map():
    with open(FOLDER_MAP_FILE, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_shipment():
    return pd.read_excel(SHIPMENT_FILE, sheet_name=SHIPMENT_SHEET)


# =========================
# HELPERS
# =========================
def normalize_text(text):
    return re.sub(r"\s+", " ", text.lower())


def extract_bkgs(text, rules):
    ids = rules["global"]["identifiers"]
    regex = ids["bkg_regex"]

    for p in ids.get("bkg_ignore_regex", []):
        text = re.sub(p, "", text, flags=re.I)

    return {ShipmentNormalizer.bkg(x) for x in re.findall(regex, text)}


def extract_etd_datetime(text):
    """
    Match: ETD 05:48 26/12/2025
    """
    m = re.search(
        r"etd\s*(\d{1,2}:\d{2})\s*(\d{1,2}/\d{1,2}/\d{4})",
        text,
        flags=re.I,
    )
    if not m:
        return None

    time_part, date_part = m.groups()
    try:
        return pd.to_datetime(f"{date_part} {time_part}", dayfirst=True)
    except Exception:
        return None


def match_event(text, rules):
    candidates = []

    for ev in rules["events"]:
        m = ev["match"]
        ok = True

        for kw in m.get("all_keywords", []):
            if kw not in text:
                ok = False

        if "any_keywords" in m:
            if not any(kw in text for kw in m["any_keywords"]):
                ok = False

        for kw in m.get("exclude_keywords", []):
            if kw in text:
                ok = False

        if ok:
            candidates.append(ev)

    if not candidates:
        return None

    return max(candidates, key=lambda x: x["priority"])


def build_precedence_index(rules):
    return {eid: i for i, eid in enumerate(rules.get("precedence", []))}


def has_late_stage_signal(text, rules):
    guard = rules.get("context_guards", {}).get("late_stage_signals", {})
    return any(k in text for k in guard.get("any_keywords", []))


def is_draft_bl_reference_only(text, rules):
    pattern = rules.get("context_guards", {}).get("draft_bl_reference_only", {}).get("pattern")
    return bool(pattern and re.search(pattern, text, flags=re.I))


def append_delay_log(df, idx, event_id):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    old = df.at[idx, "Delay_Log"] if "Delay_Log" in df else ""
    old = "" if pd.isna(old) else old
    df.at[idx, "Delay_Log"] = (old + f"\n[{now}] {event_id}").strip()


# =========================
# MAIN ENGINE
# =========================
def process_emails(emails):
    rules = load_rules()
    folder_map = load_folder_map()
    df = load_shipment()

    ref_date = datetime.now()
    norm = ShipmentNormalizer
    precedence = build_precedence_index(rules)

    allowed_customers = {
        norm.customer(c["name"])
        for g in folder_map["groups"].values()
        for c in g["customers"]
        if c.get("active", True)
    }

    for idx, row in df.iterrows():

        ship_cust = norm.customer(row.get("Customer"))
        ship_routing = norm.routing(row.get("Routing"))
        ship_bkg = norm.bkg(row.get("Bkg No"))

        if not ship_cust or not ship_routing or not ship_bkg:
            continue

        if ship_cust not in allowed_customers:
            continue

        if not norm.in_time_window(row, ref_date):
            continue

        current_status = row.get("Status_Calc") or row.get("Status")

        for mail in emails:

            if norm.customer(mail.get("customer")) != ship_cust:
                continue

            if norm.routing(mail.get("routing")) != ship_routing:
                continue

            content = normalize_text(mail["body"] + " " + mail["subject"])

            if ship_bkg not in extract_bkgs(content, rules):
                continue

            event = match_event(content, rules)
            if not event:
                continue

            # --- CONTEXT GUARD (DRAFT BL)
            if event["id"].startswith("DRAFT_BL"):
                if has_late_stage_signal(content, rules):
                    continue
                if is_draft_bl_reference_only(content, rules):
                    continue

            # --- PRECEDENCE GUARD
            if current_status in precedence and event["id"] in precedence:
                if precedence[event["id"]] < precedence[current_status]:
                    continue

            # --- UPDATE STATUS
            df.at[idx, "Status"] = event["id"]
            df.at[idx, "Status_Calc"] = event["id"]
            append_delay_log(df, idx, event["id"])

            # --- UPDATE ETD (CY–CY LOGIC)
            if event["id"] in {"LOADED_AND_ATD_CONFIRMED", "ATD"}:
                etd_dt = extract_etd_datetime(content)
                if etd_dt:
                    df.at[idx, "ETD"] = etd_dt
                    if "ETD_Original" in df.columns:
                        df.at[idx, "ETD_Original"] = etd_dt

    # ---- SAFE WRITE BACK (ONLY TARGET SHEET)
    with pd.ExcelWriter(
        SHIPMENT_FILE,
        engine="openpyxl",
        mode="a",
        if_sheet_exists="replace"
    ) as writer:
        df.to_excel(writer, sheet_name=SHIPMENT_SHEET, index=False)


# =========================
# ENTRY (TEST)
# =========================
if __name__ == "__main__":

    test_emails = [
        {
            "customer": "HML",
            "routing": "HPH-DENVER VIA OAKLAND",
            "subject": "UPDATE LOADED ON BOARD – ONE COMPETENCE 096E",
            "body": (
                "Your shipment was loaded on board successfully. "
                "VLS ONE COMPETENCE 096E – PS3 – "
                "ETD 05:48 26/12/2025."
            ),
        }
    ]

    process_emails(test_emails)
    print("EMAIL ENGINE DONE – ETD UPDATED IF FOUND")
