import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, api, buildUrl } from "@/lib/api";
import { retryPolicy } from "@/lib/hooks";
import { useSettings } from "@/lib/store";

afterEach(() => {
  vi.unstubAllGlobals();
  useSettings.setState({ apiKey: "" });
});

describe("api client", () => {
  it("builds versioned URLs and drops empty params", () => {
    const u = new URL(buildUrl("/market/candles", { symbol: "BTCUSDT", timeframe: "1H", limit: 500, provider: undefined, x: "" }));
    expect(u.pathname).toBe("/api/v1/market/candles");
    expect(u.searchParams.get("symbol")).toBe("BTCUSDT");
    expect(u.searchParams.get("limit")).toBe("500");
    expect(u.searchParams.has("provider")).toBe(false);
    expect(u.searchParams.has("x")).toBe(false);
  });

  it("sends the platform API key header only when configured", async () => {
    const fetchMock = vi.fn(async () => new Response("{}", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    await api.get("/health");
    expect((fetchMock.mock.calls[0] as unknown as [string, RequestInit])[1].headers).not.toHaveProperty("X-API-Key");
    useSettings.setState({ apiKey: "ati_test" });
    await api.get("/health");
    expect((fetchMock.mock.calls[1] as unknown as [string, RequestInit])[1].headers).toHaveProperty("X-API-Key", "ati_test");
  });

  it("maps the backend error envelope to ApiError", async () => {
    vi.stubGlobal("fetch", vi.fn(async () =>
      new Response(JSON.stringify({ error: { code: "unsupported", message: "US30 is unsupported", details: { instrument: "US30" }, request_id: "abc" } }), { status: 422 })));
    const err = await api.get("/market/candles").catch((e: ApiError) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err).toMatchObject({ status: 422, code: "unsupported", message: "US30 is unsupported", requestId: "abc", retryable: false });
  });

  it("reports an unreachable backend as a retryable network error", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("failed to fetch"); }));
    const err = (await api.get("/health").catch((e: ApiError) => e)) as ApiError;
    expect(err.code).toBe("network_error");
    expect(err.retryable).toBe(true);
  });

  it("serialises JSON bodies and handles 204", async () => {
    const fetchMock = vi.fn(async () => new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);
    await expect(api.post("/watchlists", { name: "x" })).resolves.toBeUndefined();
    const init = (fetchMock.mock.calls[0] as unknown as [string, RequestInit])[1];
    expect(init.method).toBe("POST");
    expect(init.body).toBe('{"name":"x"}');
  });

  it("retries only network/5xx failures, at most twice", () => {
    expect(retryPolicy(0, new ApiError("x", 0, "network_error"))).toBe(true);
    expect(retryPolicy(0, new ApiError("x", 503, "provider_not_configured"))).toBe(true);
    expect(retryPolicy(0, new ApiError("x", 422, "validation_failed"))).toBe(false);
    expect(retryPolicy(0, new ApiError("x", 404, "not_found"))).toBe(false);
    expect(retryPolicy(2, new ApiError("x", 500, "internal_error"))).toBe(false);
  });
});
