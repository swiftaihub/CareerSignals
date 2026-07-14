import "./globals.css";
import type { Metadata } from "next";
import type { ReactNode } from "react";

import { getAppUrl } from "@/lib/app-path";

const appUrl = getAppUrl();
const title = "CareerSignals";
const description = "Hosted, personal job-search intelligence";

export const metadata: Metadata = {
  metadataBase: new URL(`${appUrl}/`),
  title,
  description,
  alternates: { canonical: appUrl },
  openGraph: {
    type: "website",
    url: appUrl,
    siteName: title,
    title,
    description,
    images: [{
      url: `${appUrl}/illustrations/hero-career-dashboard.webp`,
      width: 1536,
      height: 1024,
      alt: "CareerSignals personalized job intelligence dashboard"
    }]
  },
  twitter: {
    card: "summary_large_image",
    title,
    description,
    images: [`${appUrl}/illustrations/hero-career-dashboard.webp`]
  }
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body suppressHydrationWarning>{children}</body>
    </html>
  );
}
