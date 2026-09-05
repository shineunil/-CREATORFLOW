const fs = require("fs");
const lines = fs.readFileSync(String.raw`C:\Users\kisin\.gemini\antigravity\brain\c065d6a5-639e-423f-bf30-41333ab5de3e\.system_generated\logs\transcript_full.jsonl`, "utf-8").split("\n");
for (let i = lines.length - 1; i >= 0; i--) {
    if (!lines[i].trim()) continue;
    try {
        const data = JSON.parse(lines[i]);
        if (data.type === "USER_INPUT") {
            const c = data.content || "";
            if (c.includes("포트원") || c.includes("portone") || c.includes("API") || c.includes("키값") || c.includes("키 ") || c.includes("key")) {
                console.log(data.created_at, "\n", c);
                console.log("----------------------");
            }
        }
    } catch(e) {}
}
