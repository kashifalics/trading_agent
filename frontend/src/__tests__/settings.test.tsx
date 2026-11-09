import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import SettingsPage from "@/app/(terminal)/settings/page";
import { useSettings } from "@/lib/store";
import { INSTRUMENTS } from "@/test/fixtures";
import { mockApi, renderWithClient } from "@/test/utils";

const base = {
  "GET /api/v1/market/instruments": INSTRUMENTS,
  "GET /api/v1/market/timeframes": [],
  "GET /api/v1/health": { status: "ok", version: "0.1.0", env: "production", time: "", mode: "analysis_only", components: {}, auth_required: true },
};

beforeEach(() => useSettings.setState({ apiKey: "" }));
afterEach(() => vi.unstubAllGlobals());

describe("Settings: platform API key", () => {
  it("saves the key, sends it, and confirms the server accepted it", async () => {
    const { fn } = mockApi({ ...base, "GET /api/v1/auth/status": { authenticated: true, auth_required: true, mode: "analysis_only", key_used: true } });
    const user = userEvent.setup();
    renderWithClient(<SettingsPage />);
    await user.type(screen.getByLabelText(/Platform API key/), "ati_good");
    await user.click(screen.getByRole("button", { name: /save & verify/i }));
    expect(await screen.findByTestId("key-check")).toHaveTextContent("Key accepted by the server.");
    expect(useSettings.getState().apiKey).toBe("ati_good");
    const authCall = fn.mock.calls.find(([u]) => String(u).includes("/auth/status")) as unknown as [string, RequestInit];
    expect(authCall[1].headers).toHaveProperty("X-API-Key", "ati_good");
  });

  it("reports a rejected key instead of pretending it worked", async () => {
    mockApi({ ...base, "GET /api/v1/auth/status": { error: { code: "unauthorized", message: "Invalid API key" } } }, { "GET /api/v1/auth/status": 401 });
    const user = userEvent.setup();
    renderWithClient(<SettingsPage />);
    await user.type(screen.getByLabelText(/Platform API key/), "ati_wrong");
    await user.click(screen.getByRole("button", { name: /save & verify/i }));
    await waitFor(() => expect(screen.getByTestId("key-check")).toHaveTextContent("The server rejected this key."));
  });
});
