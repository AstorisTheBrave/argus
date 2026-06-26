// @vitest-environment jsdom
// SPDX-License-Identifier: AGPL-3.0-or-later
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { Analytics } from "./sections_hub";

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      const body = url.includes("avg-duration")
        ? { avg_ms: 87.4 }
        : url.includes("command-stats")
          ? { rows: [["ping", 540, 42.3]] }
          : { rows: [["2026-06-20", 1200]] };
      return { ok: true, json: async () => body } as unknown as Response;
    }),
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("Analytics (bot dashboard)", () => {
  it("auto-loads data on mount when enabled, without a manual Load click", async () => {
    render(<Analytics enabled={true} token={null} />);
    await waitFor(() => expect(screen.getByText("ping")).toBeTruthy());
    expect(screen.getByText(/87\.4/)).toBeTruthy();
    expect(vi.mocked(globalThis.fetch)).toHaveBeenCalled();
  });

  it("shows the off state and fetches nothing when disabled", () => {
    render(<Analytics enabled={false} token={null} />);
    expect(screen.getByText("Analytics off")).toBeTruthy();
    expect(vi.mocked(globalThis.fetch)).not.toHaveBeenCalled();
  });
});
