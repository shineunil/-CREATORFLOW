import json
with open(r"C:\Users\kisin\.gemini\antigravity\brain\c065d6a5-639e-423f-bf30-41333ab5de3e\.system_generated\logs\transcript.jsonl", "r", encoding="utf-8") as f:
    for line in f:
        data = json.loads(line)
        if data.get("type") == "USER_INPUT":
            content = data.get("content", "")
            if "포트원" in content or "키값" in content or "portone" in content.lower():
                print(data["created_at"], content)
