const fs = require("fs");
const lines = fs.readFileSync(String.raw`C:\Users\kisin\.gemini\antigravity\brain\c065d6a5-639e-423f-bf30-41333ab5de3e\.system_generated\logs\transcript_full.jsonl`, "utf-8").split("\n");
for (const line of lines) {
    if (!line.trim()) continue;
    try {
        const data = JSON.parse(line);
        if (data.type === "USER_INPUT") {
            const c = data.content || "";
            if (c.includes("포트원") || c.includes("portone") || c.includes("로그아웃")) {
                console.log(data.created_at, "\n", c);
                console.log("----------------------");
            }
        }
    } catch(e) {}
}
