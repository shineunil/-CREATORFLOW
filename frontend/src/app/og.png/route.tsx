import { ImageResponse } from "next/og";

// 링크 미리보기(카카오톡·X·페이스북·디스코드 등)용 1200×630 이미지.
// 기본 글꼴에 한글이 없어서, 두 언어에 같이 쓰도록 영어와 숫자만 넣는다.
// 주소가 .png로 끝나 proxy.ts의 로그인 확인을 거치지 않는다.

const CANDIDATES = [
  { name: "A", label: "Original", vph: 42, color: "#71717a" },
  { name: "B", label: "Winner", vph: 118, color: "#06b6d4" },
  { name: "C", label: "Variant", vph: 67, color: "#8b5cf6" },
];
const MAX_VPH = 118;

export function GET() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: "64px 72px",
          backgroundColor: "#050505",
          backgroundImage: "radial-gradient(circle at 85% 10%, rgba(6,182,212,0.22), transparent 45%), radial-gradient(circle at 10% 95%, rgba(139,92,246,0.18), transparent 40%)",
          color: "#f4f4f5",
          fontFamily: "sans-serif",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
          <div
            style={{
              width: 56,
              height: 56,
              borderRadius: 14,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              backgroundImage: "linear-gradient(135deg, #06b6d4, #3b82f6)",
              fontSize: 26,
              fontWeight: 800,
              color: "white",
            }}
          >
            TF
          </div>
          <div style={{ fontSize: 34, fontWeight: 800, letterSpacing: 1 }}>ThumbnailFlow</div>
        </div>

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", gap: 48 }}>
          <div style={{ display: "flex", flexDirection: "column", maxWidth: 600 }}>
            <div style={{ fontSize: 68, fontWeight: 900, lineHeight: 1.1 }}>YouTube Thumbnail</div>
            <div style={{ fontSize: 68, fontWeight: 900, lineHeight: 1.1, color: "#22d3ee" }}>A/B Testing</div>
            <div style={{ fontSize: 28, color: "#a1a1aa", marginTop: 24, lineHeight: 1.4 }}>
              Rotate thumbnails and titles on your live video. Keep the one with the most views per hour.
            </div>
          </div>

          <div style={{ display: "flex", alignItems: "flex-end", gap: 22, height: 300 }}>
            {CANDIDATES.map((c) => (
              <div key={c.name} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 10 }}>
                <div style={{ fontSize: 24, fontWeight: 800, color: c.name === "B" ? "#22d3ee" : "#d4d4d8" }}>{`${c.vph}/h`}</div>
                <div
                  style={{
                    width: 92,
                    height: Math.round((c.vph / MAX_VPH) * 210),
                    borderRadius: 12,
                    backgroundColor: c.color,
                    boxShadow: c.name === "B" ? "0 0 40px rgba(6,182,212,0.55)" : "none",
                  }}
                />
                <div style={{ fontSize: 22, fontWeight: 700 }}>{c.name}</div>
                <div style={{ fontSize: 16, color: "#a1a1aa" }}>{c.label}</div>
              </div>
            ))}
          </div>
        </div>

        <div style={{ display: "flex", fontSize: 22, color: "#71717a" }}>trythumbnailflow.com · Free to start</div>
      </div>
    ),
    { width: 1200, height: 630 }
  );
}
