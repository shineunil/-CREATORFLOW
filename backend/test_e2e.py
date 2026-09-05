import jwt
import requests
import json
import time
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# Database setup
engine = create_engine("sqlite:///./youtube_ab_test.db", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

from models import User, Channel, PlanType, ABTest

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

db = next(get_db())

print("--- E2E TEST START ---")
print("1. Creating a fresh test user and channel (BASIC)...")

test_email = f"test_e2e_{int(time.time())}@creatorflow.io"
user = User(email=test_email, plan=PlanType.BASIC)
db.add(user)
db.commit()
db.refresh(user)

channel = Channel(
    user_id=user.id,
    youtube_channel_id=f"UC_{int(time.time())}",
    channel_title="E2E Test Channel",
    oauth_refresh_token="mock_refresh"
)
db.add(channel)
db.commit()
db.refresh(channel)

print(f"-> Created User: {user.email}, Plan: {user.plan}")
print(f"-> Created Channel: {channel.channel_title} (ID: {channel.id})")

token = jwt.encode({"sub": str(channel.id)}, "super_secret_jwt_key_for_dev_only", algorithm="HS256")
headers = {"Authorization": f"Bearer {token}"}
API_BASE = "http://localhost:8000"

def create_test(video_id, swap_interval=60, num_variations=2):
    variations = [
        {"name": "A", "title_text": "Original Title", "is_control": True, "thumbnail_image_url": "http://example.com/a.png"}
    ]
    for i in range(1, num_variations + 1):
        char = chr(65 + i)
        variations.append({"name": char, "title_text": f"Var {char}", "is_control": False, "thumbnail_image_url": f"http://example.com/{char}.png"})
        
    payload = {
        "youtube_video_id": video_id,
        "swap_interval_minutes": swap_interval,
        "duration_hours": 24,
        "variations": variations
    }
    return requests.post(f"{API_BASE}/api/tests", json=payload, headers=headers)

vid_prefix = f"vid_{int(time.time())}"

print("\n2. Creating 1st Test...")
res1 = create_test(f"{vid_prefix}_1")
print(f"Response: {res1.status_code} {res1.text}")
assert res1.status_code == 200, "1st test failed"
test_id_1 = res1.json()["id"]

print("\n3. Testing [Simultaneous Limit]...")
res2 = create_test(f"{vid_prefix}_2")
print(f"Response: {res2.status_code} {res2.text}")
assert res2.status_code == 403, "Failed to block simultaneous test"

print("\n4. Canceling 1st Test...")
res_del = requests.delete(f"{API_BASE}/api/tests/{test_id_1}", headers=headers)
print(f"Delete Response: {res_del.status_code}")

print("\n5. Testing [Swap Interval 30m Limit]...")
res_30m = create_test(f"{vid_prefix}_3", swap_interval=30)
print(f"Response: {res_30m.status_code} {res_30m.text}")
assert res_30m.status_code == 403, "Failed to block 30m swap"

print("\n6. Testing [Variation Count Limit] (A,B,C,D,E)...")
res_vars = create_test(f"{vid_prefix}_4", num_variations=4)
print(f"Response: {res_vars.status_code} {res_vars.text}")
assert res_vars.status_code == 403, "Failed to block >3 candidates"

print("\n7. Using up monthly quota (remaining 3)...")
for i in range(2, 5):
    res = create_test(f"{vid_prefix}_month_{i}")
    print(f"Test {i} creation: {res.status_code}")
    assert res.status_code == 200, f"Test {i} failed"
    requests.delete(f"{API_BASE}/api/tests/{res.json()['id']}", headers=headers)
    
print("\n8. Testing [Monthly Quota Block] (5th test)...")
res_5 = create_test(f"{vid_prefix}_blocked")
print(f"Response: {res_5.status_code} {res_5.text}")
assert res_5.status_code == 403, "Failed to block 5th test"

print("\n9. Upgrading to PRO...")
res_upgrade = requests.post(f"{API_BASE}/api/checkout/upgrade-test", headers=headers)
print(f"Upgrade Response: {res_upgrade.status_code}")

print("\n10. Retrying [Monthly Quota] as PRO...")
res_pro_1 = create_test(f"{vid_prefix}_pro_1")
print(f"Response: {res_pro_1.status_code}")
assert res_pro_1.status_code == 200

print("\n11. Retrying [Simultaneous Limit] as PRO...")
res_pro_2 = create_test(f"{vid_prefix}_pro_2")
print(f"Response: {res_pro_2.status_code}")
assert res_pro_2.status_code == 200

print("\n12. Retrying [Swap Interval 30m] as PRO...")
requests.delete(f"{API_BASE}/api/tests/{res_pro_2.json()['id']}", headers=headers)
res_pro_30m = create_test(f"{vid_prefix}_pro_30m", swap_interval=30)
print(f"Response: {res_pro_30m.status_code}")
assert res_pro_30m.status_code == 200

print("\n13. Retrying [Variation Count 5] as PRO...")
requests.delete(f"{API_BASE}/api/tests/{res_pro_30m.json()['id']}", headers=headers)
res_pro_vars = create_test(f"{vid_prefix}_pro_vars", num_variations=4)
print(f"Response: {res_pro_vars.status_code}")
assert res_pro_vars.status_code == 200

print("\n✅ ALL E2E TESTS PASSED SUCCESSFULLY! ✅")
