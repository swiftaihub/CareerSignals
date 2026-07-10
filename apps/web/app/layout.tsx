import "./globals.css";
import type { ReactNode } from "react";

export const metadata = {
  title: "CareerSignal Personal Dashboard",
  description: "Enterprise-grade personal job-search intelligence dashboard"
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body suppressHydrationWarning>{children}</body>
    </html>
  );
}
