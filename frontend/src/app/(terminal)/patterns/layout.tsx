import type { Metadata } from "next";

export const metadata: Metadata = { title: "Historical Patterns" };

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
