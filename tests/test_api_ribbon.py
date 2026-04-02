import requests
import json

BASE_URL = "http://localhost:8000"

def test_rates():
    # Test POL, POD search like the Ribbon does
    payload = {
        "pol": "HPH",
        "pod": "USLAX",
        "place": "DENVER",
        "career": "CMA",
        "note": "SOC"
    }
    
    print(f"Testing search: {payload}")
    try:
        # The Ribbon typically calls an endpoint that returns a row or list of rows
        # Based on erp_router.py (assuming it has a rates endpoint)
        # Let's check common endpoints
        resp = requests.get(f"{BASE_URL}/api/erp/rates-matrix", params=payload)
        if resp.status_code == 200:
            data = resp.json()
            print(f"Success! Found {len(data)} rows.")
            if data:
                print(f"First row: {data[0]}")
        else:
            print(f"Failed with status: {resp.status_code}")
            print(resp.text)
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_rates()
