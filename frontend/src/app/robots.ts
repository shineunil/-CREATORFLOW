import type { MetadataRoute } from "next";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        // robots 규칙은 앞부분 일치라 "/pricing" 차단이 "/pricing-public"까지 막으므로, 더 긴 허용 규칙으로 풀어 준다.
        allow: ["/", "/pricing-public"],
        disallow: [
          "/dashboard",
          "/connect",
          "/new",
          "/settings",
          "/admin",
          "/videos",
          "/analytics",
          "/history",
          "/projects",
          "/pricing",
        ],
      },
    ],
    sitemap: "https://trythumbnailflow.com/sitemap.xml",
  };
}
