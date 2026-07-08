import "./globals.css";
import type { ReactNode } from "react";

export const metadata = {
  title: "CareerSignal",
  description: "Job-search intelligence dashboard"
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
