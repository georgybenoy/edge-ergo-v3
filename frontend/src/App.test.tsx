import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import App from "./App";

vi.mock("./lib/supabase", () => ({
  getMissingEnvConfig: () => [],
  supabase: {
    auth: {
      getSession: vi.fn().mockResolvedValue({ data: { session: null }, error: null }),
      onAuthStateChange: vi.fn(() => ({
        data: { subscription: { unsubscribe: vi.fn() } },
      })),
    },
  },
}));

describe("App Root", () => {
  beforeEach(() => {
    window.history.pushState({}, "", "/");
  });

  it("renders EdgeErgo brand and redirects to login when unauthenticated", async () => {
    render(<App />);
    await waitFor(() => {
      const heading = screen.getByRole("heading", { level: 1 });
      expect(heading).toBeInTheDocument();
      expect(heading).toHaveTextContent(/Edge.*Ergo/i);
      expect(
        screen.getByRole("button", { name: /Sign in to Dashboard/i })
      ).toBeInTheDocument();
    });
  });
});
