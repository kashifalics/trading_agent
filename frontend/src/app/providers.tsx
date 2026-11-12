"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { AUTO_REFRESH_MS, retryPolicy } from "@/lib/hooks";
import { useSettings } from "@/lib/store";

export function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(
    // Every page refreshes by itself: data is fetched again every minute while the page is open (pages that change faster set a shorter
    // interval in lib/hooks.ts) and as soon as you come back to the tab. Fixed reference data opts out with refetchInterval: false.
    () => new QueryClient({ defaultOptions: { queries: { staleTime: 10_000, retry: retryPolicy, refetchOnWindowFocus: true, refetchInterval: AUTO_REFRESH_MS } } }),
  );
  useEffect(() => {
    void useSettings.persist.rehydrate();
  }, []);
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
