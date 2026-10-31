import type { Metadata, Viewport } from "next";
import "./globals.css";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "AI Trading Intelligence",
  description: "Analysis-only market intelligence terminal: BUY / SELL / WAIT with evidence. No order execution.",
};

export const viewport: Viewport = { width: "device-width", initialScale: 1, themeColor: "#0a0e17" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen font-sans antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
