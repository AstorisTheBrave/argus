// @vitest-environment jsdom
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SetupWizard } from "./SetupWizard";

function advanceToResult() {
  fireEvent.click(screen.getByText("Start"));
  fireEvent.click(screen.getByText("Next")); // token -> basics
  fireEvent.click(screen.getByText("Next")); // basics -> features
  fireEvent.click(screen.getByText("Next")); // features -> host
  fireEvent.click(screen.getByText("Generate my setup")); // host -> result
}

describe("SetupWizard", () => {
  it("walks the funnel and generates the docker file set with steps", () => {
    render(<SetupWizard />);
    expect(screen.getByText(/no coding required/i)).toBeTruthy();

    advanceToResult();

    expect(screen.getByText("You're ready")).toBeTruthy();
    expect(screen.getByText(".env")).toBeTruthy();
    expect(screen.getByText("docker-compose.yml")).toBeTruthy();
    expect(screen.getByText(/docker compose up/i)).toBeTruthy();
    expect(screen.getByText("Download all files")).toBeTruthy();
  });

  it("reveals the ClickHouse field only when analytics is enabled", () => {
    render(<SetupWizard />);
    fireEvent.click(screen.getByText("Start")); // -> token
    fireEvent.click(screen.getByText("Next")); // -> basics
    fireEvent.click(screen.getByText("Next")); // -> features

    expect(screen.queryByPlaceholderText(/clickhouse:\/\//)).toBeNull();
    fireEvent.click(screen.getByLabelText(/Per-server analytics/i));
    expect(screen.getByPlaceholderText(/clickhouse:\/\//)).toBeTruthy();
  });
});
