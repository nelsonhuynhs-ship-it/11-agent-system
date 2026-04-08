# -*- coding: utf-8 -*-
"""Health check - self-contained, no external imports."""
import json, sys, time
try:
    import httpx
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "httpx", "-q"])
    import httpx

def check():
    r = {"timestamp": time.strftime("%Y-%m-%d %H:%M:%S")}
    for name, url in [("vps_api","http://14.225.207.145:8100/health"), ("vps_webapp","http://14.225.207.145:3003")]:
        try:
            t0 = time.time()
            resp = httpx.get(url, timeout=10, follow_redirects=True)
            r[name] = {"status": "ok" if resp.status_code < 500 else "error", "code": resp.status_code, "ms": int((time.time()-t0)*1000)}
        except Exception as e:
            r[name] = {"status": "down", "error": str(e)[:80]}
    try:
        import subprocess as sp
        out = sp.run(["tasklist", "/FI", "IMAGENAME eq OUTLOOK.EXE"], capture_output=True, text=True, timeout=5)
        r["outlook"] = "running" if "OUTLOOK.EXE" in out.stdout else "not_running"
    except:
        r["outlook"] = "unknown"
    r["overall"] = "healthy" if r.get("vps_api",{}).get("status")=="ok" else "degraded"
    return r

print(json.dumps(check(), ensure_ascii=False, indent=2))
