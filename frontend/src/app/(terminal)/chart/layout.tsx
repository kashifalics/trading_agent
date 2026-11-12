import type { Metadata } from "next";

export const metadata: Metadata = { title: "Chart Analysis" };

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
