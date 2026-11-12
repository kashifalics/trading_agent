import type { Metadata } from "next";
import { AppShell } from "@/components/layout/app-shell";

export const metadata: Metadata = { title: "Overview" }; // pages below set their own title in their layout.tsx

export default function TerminalLayout({ children }: { children: React.ReactNode }) {
  return <AppShell>{children}</AppShell>;
}
