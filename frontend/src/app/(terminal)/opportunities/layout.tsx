import type { Metadata } from "next";

export const metadata: Metadata = { title: "Trade Opportunities" };

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
