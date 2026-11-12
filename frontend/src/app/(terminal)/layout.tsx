import type { Metadata } from "next";
import { AppShell } from "@/components/layout/app-shell";

// the Overview's own title, and the suffix for the pages below (each names itself in its layout.tsx)
export const metadata: Metadata = { title: { absolute: "Overview · AI Trading Intel", template: "%s · AI Trading Intel" } };

export default function TerminalLayout({ children }: { children: React.ReactNode }) {
  return <AppShell>{children}</AppShell>;
}
