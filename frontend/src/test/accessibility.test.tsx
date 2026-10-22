import { describe, it, expect, vi } from "vitest";
import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import axe from "axe-core";
import { AppShell } from "../components/layout/AppShell";
import { LoginPage } from "../pages/LoginPage";
import { SettingsPage } from "../pages/SettingsPage";
import { AuthProvider } from "../features/auth/AuthContext";
import { UserProfileProvider } from "../features/auth/UserProfileContext";

// Mock Supabase
vi.mock("../lib/supabase", () => ({
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

describe("Accessibility Smoke Tests (axe-core)", () => {
  it("LoginPage has no critical accessibility violations", async () => {
    const { container } = render(
      <MemoryRouter>
        <AuthProvider>
          <LoginPage />
        </AuthProvider>
      </MemoryRouter>
    );

    const results = await axe.run(container, {
      rules: {
        // Exclude color-contrast in jsdom environment if computed styles are unavailable
        "color-contrast": { enabled: false },
      },
    });

    const seriousViolations = results.violations.filter(
      (v) => v.impact === "critical" || v.impact === "serious"
    );
    expect(seriousViolations).toEqual([]);
  });

  it("AppShell has no critical accessibility violations", async () => {
    const { container } = render(
      <MemoryRouter>
        <AuthProvider>
          <UserProfileProvider>
            <AppShell>
              <div>Dashboard Content</div>
            </AppShell>
          </UserProfileProvider>
        </AuthProvider>
      </MemoryRouter>
    );

    const results = await axe.run(container, {
      rules: {
        "color-contrast": { enabled: false },
      },
    });

    const seriousViolations = results.violations.filter(
      (v) => v.impact === "critical" || v.impact === "serious"
    );
    expect(seriousViolations).toEqual([]);
  });

  it("SettingsPage has no critical accessibility violations", async () => {
    const { container } = render(
      <MemoryRouter>
        <AuthProvider>
          <UserProfileProvider>
            <SettingsPage />
          </UserProfileProvider>
        </AuthProvider>
      </MemoryRouter>
    );

    const results = await axe.run(container, {
      rules: {
        "color-contrast": { enabled: false },
      },
    });

    const seriousViolations = results.violations.filter(
      (v) => v.impact === "critical" || v.impact === "serious"
    );
    expect(seriousViolations).toEqual([]);
  }, 30000);

  it("OverviewPage has no critical accessibility violations", async () => {
    const { OverviewPage } = await import("../pages/OverviewPage");
    const { container } = render(
      <MemoryRouter>
        <AuthProvider>
          <UserProfileProvider>
            <OverviewPage />
          </UserProfileProvider>
        </AuthProvider>
      </MemoryRouter>
    );

    const results = await axe.run(container, {
      rules: {
        "color-contrast": { enabled: false },
      },
    });

    const seriousViolations = results.violations.filter(
      (v) => v.impact === "critical" || v.impact === "serious"
    );
    expect(seriousViolations).toEqual([]);
  }, 30000);

  it("AssessmentsPage has no critical accessibility violations", async () => {
    const { AssessmentsPage } = await import("../pages/AssessmentsPage");
    const { ToastProvider } = await import("../components/ui/Toast");
    const { container } = render(
      <MemoryRouter>
        <AuthProvider>
          <UserProfileProvider>
            <ToastProvider>
              <AssessmentsPage />
            </ToastProvider>
          </UserProfileProvider>
        </AuthProvider>
      </MemoryRouter>
    );

    const results = await axe.run(container, {
      rules: {
        "color-contrast": { enabled: false },
      },
    });

    const seriousViolations = results.violations.filter(
      (v) => v.impact === "critical" || v.impact === "serious"
    );
    expect(seriousViolations).toEqual([]);
  }, 30000);

  it("DevicesPage has no critical accessibility violations", async () => {
    const { DevicesPage } = await import("../pages/DevicesPage");
    const { ToastProvider } = await import("../components/ui/Toast");
    const { container } = render(
      <MemoryRouter>
        <AuthProvider>
          <UserProfileProvider>
            <ToastProvider>
              <DevicesPage />
            </ToastProvider>
          </UserProfileProvider>
        </AuthProvider>
      </MemoryRouter>
    );

    const results = await axe.run(container, {
      rules: {
        "color-contrast": { enabled: false },
      },
    });

    const seriousViolations = results.violations.filter(
      (v) => v.impact === "critical" || v.impact === "serious"
    );
    expect(seriousViolations).toEqual([]);
  }, 30000);

  it("ReportsPage has no critical accessibility violations", async () => {
    const { ReportsPage } = await import("../pages/ReportsPage");
    const { ToastProvider } = await import("../components/ui/Toast");
    const { container } = render(
      <MemoryRouter>
        <AuthProvider>
          <UserProfileProvider>
            <ToastProvider>
              <ReportsPage />
            </ToastProvider>
          </UserProfileProvider>
        </AuthProvider>
      </MemoryRouter>
    );

    const results = await axe.run(container, {
      rules: {
        "color-contrast": { enabled: false },
      },
    });

    const seriousViolations = results.violations.filter(
      (v) => v.impact === "critical" || v.impact === "serious"
    );
    expect(seriousViolations).toEqual([]);
  }, 30000);
});
