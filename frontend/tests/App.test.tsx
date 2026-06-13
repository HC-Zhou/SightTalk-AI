import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import App from "../src/App";

describe("App", () => {
  it("renders the PC video call interface", () => {
    render(<App />);

    expect(screen.getByRole("heading", { name: "SightTalk AI" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "实时字幕" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "开始通话" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "提交发言" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "挂断" })).toBeTruthy();
    expect(screen.getAllByText("等待连接").length).toBeGreaterThan(0);
  });
});
