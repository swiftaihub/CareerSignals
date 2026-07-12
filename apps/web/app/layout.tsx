import "./globals.css";
import type { ReactNode } from "react";

export const metadata = {
  title: "CareerSignals",
  description: "Hosted, personal job-search intelligence"
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body suppressHydrationWarning>{children}</body>
    </html>
  );
}
