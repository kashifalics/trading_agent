import type { Metadata } from "next";

export const metadata: Metadata = { title: "Engine v1 checklist" };

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
