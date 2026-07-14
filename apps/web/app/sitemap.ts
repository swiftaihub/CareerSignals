import type { MetadataRoute } from "next";

import { getAppUrl } from "@/lib/app-path";

export default function sitemap(): MetadataRoute.Sitemap {
  const appUrl = getAppUrl();
  return [
    { url: appUrl, changeFrequency: "weekly", priority: 1 },
    { url: `${appUrl}/pricing`, changeFrequency: "monthly", priority: 0.7 }
  ];
}
