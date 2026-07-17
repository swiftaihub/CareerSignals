import type { MetadataRoute } from "next";

import { getBasePath, withBasePath } from "@/lib/app-path";

export default function manifest(): MetadataRoute.Manifest {
  const basePath = getBasePath();
  return {
    name: "CareerSignals",
    short_name: "CareerSignals",
    description: "Hosted, personal job-search intelligence",
    id: withBasePath("/"),
    start_url: withBasePath("/"),
    scope: `${basePath}/` || "/",
    display: "standalone",
    background_color: "#ffffff",
    theme_color: "#0f766e",
    icons: [{
      src: withBasePath("/careersignals-icon.svg"),
      sizes: "any",
      type: "image/svg+xml",
      purpose: "any"
    }]
  };
}
