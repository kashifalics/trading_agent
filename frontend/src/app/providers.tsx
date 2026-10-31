"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { retryPolicy } from "@/lib/hooks";
import { useSettings } from "@/lib/store";

export function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(
    () => new QueryClient({ defaultOptions: { queries: { staleTime: 10_000, retry: retryPolicy, refetchOnWindowFocus: false } } }),
  );
  useEffect(() => {
    void useSettings.persist.rehydrate();
  }, []);
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
