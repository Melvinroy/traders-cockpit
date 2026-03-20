import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Trader's Cockpit",
  description: "Semi-automated swing-trade management cockpit"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
