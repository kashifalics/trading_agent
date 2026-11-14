import type { Metadata } from "next";

export const metadata: Metadata = { title: "Trade History" };

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
