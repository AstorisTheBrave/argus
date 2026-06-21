// @vitest-environment jsdom
// SPDX-License-Identifier: AGPL-3.0-or-later
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { Analytics } from "./Analytics";

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      const body = url.includes("avg-duration")
        ? { avg_ms: 12.5 }
        : { rows: [["ping", 10]] };
      return { ok: true, json: async () => body } as unknown as Response;
    }),
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("Analytics", () => {
  it("loads top commands and avg duration for a guild", async () => {
    render(<Analytics token={null} />);
    fireEvent.change(screen.getByLabelText("guild id"), { target: { value: "42" } });
    fireEvent.click(screen.getByText("Load"));
    await waitFor(() => expect(screen.getByText("ping")).toBeTruthy());
    expect(screen.getByText("12.5 ms")).toBeTruthy();
  });

  it("does nothing without a guild id", () => {
    render(<Analytics token={null} />);
    fireEvent.click(screen.getByText("Load"));
    expect(vi.mocked(globalThis.fetch)).not.toHaveBeenCalled();
  });
});
