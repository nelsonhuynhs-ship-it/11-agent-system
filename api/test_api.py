import sys
sys.stdout.reconfigure(encoding='utf-8')
import httpx

r = httpx.get('http://localhost:8000/api/shipments')
d = r.json()
print(f"Total: {d['total']} shipments from API")
for s in d['shipments'][:10]:
    sid = s['id'][:20].ljust(20)
    cust = s['customer'][:15].ljust(15)
    stage = s['stage'][:22].ljust(22)
    risk = s['risk_level'] or 'OK'
    print(f"  {sid} | {cust} | {stage} | risk: {risk}")
