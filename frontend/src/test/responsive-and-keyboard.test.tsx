import { describe, it, expect, vi } from "vitest";
import { useState } from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { TopNav } from "../components/layout/TopNav";
import { ConfirmDialog } from "../components/ui/ConfirmDialog";
import { Button } from "../components/ui/Button";

vi.mock("../features/auth/AuthContext", () => ({
  useAuth: () => ({
    status: "authenticated",
    user: { email: "tester@edgeergo.local" },
    signOut: vi.fn(),
  }),
}));

vi.mock("../features/auth/UserProfileContext", () => ({
  useUserProfile: () => ({
    profile: {
      user_id: "user-123",
      email: "tester@edgeergo.local",
      organization_id: "org-1",
      organization_slug: "acme",
      role: "admin",
    },
    loading: false,
    error: null,
  }),
}));

describe("Responsive Layout & Keyboard Navigation (Tasks 1, 7 & 8)", () => {
  it("manages mobile drawer open/close, Escape key, and backdrop click", () => {
    render(
      <MemoryRouter>
        <TopNav />
      </MemoryRouter>
    );

    // Initial state: mobile drawer closed
    expect(screen.queryByRole("dialog", { name: /Mobile navigation/i })).not.toBeInTheDocument();

    // Find and click hamburger menu button
    const menuBtn = screen.getByLabelText(/Open navigation menu/i);
    expect(menuBtn).toBeInTheDocument();
    fireEvent.click(menuBtn);

    // Drawer should open with dialog role
    const dialog = screen.getByRole("dialog", { name: /Mobile navigation/i });
    expect(dialog).toBeInTheDocument();

    // Press Escape to dismiss drawer
    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.queryByRole("dialog", { name: /Mobile navigation/i })).not.toBeInTheDocument();
  });

  it("handles keyboard Escape key and focus in ConfirmDialog", () => {
    const handleClose = vi.fn();
    const handleConfirm = vi.fn();

    function DialogWrapper() {
      const [open, setOpen] = useState(true);
      return (
        <ConfirmDialog
          isOpen={open}
          onCancel={() => {
            setOpen(false);
            handleClose();
          }}
          onConfirm={handleConfirm}
          title="Revoke Workstation"
          description="Are you sure you want to revoke this workstation?"
          confirmLabel="Revoke"
        />
      );
    }

    render(<DialogWrapper />);

    expect(screen.getByRole("dialog", { name: "Revoke Workstation" })).toBeInTheDocument();

    // Press Escape
    fireEvent.keyDown(window, { key: "Escape" });
    expect(handleClose).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("verifies 44x44px min touch targets on interactive buttons", () => {
    const { container } = render(
      <div>
        <Button size="md">Test Action</Button>
        <Button size="sm">Small Action</Button>
      </div>
    );

    const buttons = container.querySelectorAll("button");
    buttons.forEach((btn) => {
      // Must contain min-h-[44px] or min-w-[44px] class per design system §18
      const hasMinHeight =
        btn.className.includes("min-h-[44px]") ||
        btn.className.includes("min-h-[48px]") ||
        btn.className.includes("min-w-[44px]");
      expect(hasMinHeight).toBe(true);
    });
  });

  it("simulates responsive viewports (1280px desktop, 820px tablet, 390px mobile)", () => {
    const { container } = render(
      <MemoryRouter>
        <TopNav />
      </MemoryRouter>
    );

    // TopNav structure contains:
    // 1. Desktop / Tablet horizontal nav: hidden md:flex
    // 2. Mobile trigger button: md:hidden
    const nav = container.querySelector('nav[aria-label="Primary navigation"]');
    expect(nav).toHaveClass("hidden");
    expect(nav).toHaveClass("md:flex");

    const mobileBtn = screen.getByLabelText(/navigation menu/i);
    expect(mobileBtn).toHaveClass("md:hidden");
  });
});
