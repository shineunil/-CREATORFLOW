import jwt
import requests
import json
import time

token = jwt.encode({"sub": "2"}, "super_secret_jwt_key_for_dev_only", algorithm="HS256")
headers = {"Authorization": f"Bearer {token}"}
API_BASE = "http://localhost:8000"

res = requests.get(f"{API_BASE}/api/tests", headers=headers)
print(res.json())
tests = res.json().get("tests", [])
for t in tests:
    print(f"Deleting {t['test_id']}...")
    del_res = requests.delete(f"{API_BASE}/api/tests/{t['test_id']}", headers=headers)
    print(del_res.status_code, del_res.text)
