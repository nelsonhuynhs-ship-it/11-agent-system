import sys
from pathlib import Path
sys.path.insert(0, str(Path(r"D:\NELSON\2. Areas\Engine_test")))
from email_engine.web_server import DEFAULT_DESTINATIONS
print("DEFAULT_DESTINATIONS:", DEFAULT_DESTINATIONS)
print("count:", len(DEFAULT_DESTINATIONS))

# Also resolve config for shing.cheung@vexos.cn
import pandas as pd
from email_engine.shared.paths import CNEE_MASTER_XLSX
df = pd.read_excel(CNEE_MASTER_XLSX, dtype=str)
row = df[df["EMAIL"].str.lower().str.strip() == "shing.cheung@vexos.cn"]
if len(row) > 0:
    row_dict = row.iloc[0].to_dict()
    from email_engine.core.rule_engine import resolve_config
    config = resolve_config(row_dict, user_markup=20)
    print("config.destination:", config.get("destination"))
    print("config.pol:", config.get("pol"))
    print("config.arb_origin:", config.get("arb_origin"))
