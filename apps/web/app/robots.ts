import type { MetadataRoute } from "next";

import { getAppUrl, withBasePath } from "@/lib/app-path";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: withBasePath("/"),
      disallow: [
        "/admin",
        "/api",
        "/auth",
        "/dashboard",
        "/jobs",
        "/settings",
        "/top-matches",
        "/skill-gap",
        "/companies"
      ].map((path) => withBasePath(path))
    },
    sitemap: `${getAppUrl()}/sitemap.xml`
  };
}
