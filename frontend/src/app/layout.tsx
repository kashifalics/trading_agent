import type { Metadata, Viewport } from "next";
import { Poppins } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";

const sans = Poppins({ subsets: ["latin"], weight: ["400", "500", "600", "700"], variable: "--font-sans", display: "swap" });

export const metadata: Metadata = {
  title: { default: "AI Trading Intelligence", template: "%s · AI Trading Intel" }, // each route's layout names its page
  description: "Analysis-only market intelligence terminal: BUY / SELL / WAIT with evidence. No order execution.",
};

export const viewport: Viewport = { width: "device-width", initialScale: 1, themeColor: "#f3f8fd" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={sans.variable}>
      <body className="min-h-screen font-sans antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
