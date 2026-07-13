import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

function readBasePath(value) {
  const candidate = value?.trim() ?? "";
  if (!candidate || candidate === "/") return "";
  if (
    !candidate.startsWith("/")
    || candidate.startsWith("//")
    || candidate.endsWith("/")
    || candidate.includes("?")
    || candidate.includes("#")
    || /[\\\u0000-\u001f\u007f]/.test(candidate)
  ) {
    throw new Error(
      "NEXT_PUBLIC_BASE_PATH must be empty or start with one slash and have no trailing slash."
    );
  }
  if (candidate.slice(1).split("/").some((part) => !part || part === "." || part === "..")) {
    throw new Error("NEXT_PUBLIC_BASE_PATH contains an invalid path segment.");
  }
  return candidate;
}

const basePath = readBasePath(process.env.NEXT_PUBLIC_BASE_PATH);

/** @type {import('next').NextConfig} */
const nextConfig = {
  basePath,
  async headers() {
    return [{
      source: "/:path*",
      headers: [
        { key: "X-Content-Type-Options", value: "nosniff" },
        { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
        { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        { key: "X-Frame-Options", value: "DENY" }
      ]
    }];
  },
  turbopack: {
    root: dirname(fileURLToPath(import.meta.url))
  }
};

export default nextConfig;
