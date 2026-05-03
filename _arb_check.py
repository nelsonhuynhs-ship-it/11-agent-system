import sys
from pathlib import Path
sys.path.insert(0, str(Path(r"D:\NELSON\2. Areas\Engine_test\email_engine\core")))
from auto_rate_builder import build_rate_table_for_customer

dests = "USLAX,USSAV,USNYC,USHOU,USMIA,USTIW,USATL,USCHI,USDAL,USDEN"
for pol in ("HCM", "HPH"):
    r = build_rate_table_for_customer(pol=pol, destinations=dests, markup=20, top_per_route=3)
    rates = r.get("rates", [])
    by_pod = {}
    for rr in rates:
        pod = str(rr.get("pod_code", "")).upper()
        by_pod.setdefault(pod, []).append(rr)
    print(f"=== {pol} === total rates: {len(rates)} rates_found: {r.get('rates_found')}")
    for pod in dests.split(","):
        lst = by_pod.get(pod, [])
        if lst:
            tops = ", ".join(f"{x.get('carrier')}=${x.get('rate_40')} ({x.get('rate_type')})" for x in lst[:3])
        else:
            tops = "EMPTY"
        print(f"  {pod}: {len(lst)} -> {tops}")
