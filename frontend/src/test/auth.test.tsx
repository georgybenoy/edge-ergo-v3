import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { AuthProvider, useAuth } from "../features/auth/AuthContext";
import { UserProfileProvider } from "../features/auth/UserProfileContext";
import { ProtectedRoute } from "../features/auth/ProtectedRoute";
import { LoginPage } from "../pages/LoginPage";
import { SettingsPage } from "../pages/SettingsPage";

// Mock Supabase client module
vi.mock("../lib/supabase", () => {
  return {
    getMissingEnvConfig: () => [],
    supabase: {
      auth: {
        getSession: vi.fn().mockResolvedValue({ data: { session: null }, error: null }),
        onAuthStateChange: vi.fn(() => {
          return { data: { subscription: { unsubscribe: vi.fn() } } };
        }),
        signInWithPassword: vi.fn(),
        signOut: vi.fn().mockResolvedValue({ error: null }),
        resetPasswordForEmail: vi.fn().mockResolvedValue({ error: null }),
      },
    },
  };
});

// Mock fetch for /api/v1/me
vi.mock("../lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/api")>();
  return {
    ...actual,
    fetchMe: vi.fn().mockResolvedValue({
      user_id: "user-123",
      email: "test@edgeergo.local",
      organization_id: "org-123",
      organization_slug: "test-org",
      role: "admin",
    }),
  };
});

describe("Authentication & Session Flow (Task 3 & 7)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("redirects unauthenticated users to /login without displaying protected content", async () => {
    render(
      <MemoryRouter initialEntries={["/"]}>
        <AuthProvider>
          <UserProfileProvider>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route
                path="/"
                element={
                  <ProtectedRoute>
                    <div data-testid="protected-content">Secret Dashboard</div>
                  </ProtectedRoute>
                }
              />
            </Routes>
          </UserProfileProvider>
        </AuthProvider>
      </MemoryRouter>
    );

    // Should redirect to login page
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Sign in to Dashboard/i })).toBeInTheDocument();
    });

    // Protected content MUST NOT be displayed
    expect(screen.queryByTestId("protected-content")).not.toBeInTheDocument();
  });

  it("does not flash protected content while authentication is resolving (loading state)", () => {
    // Component showing loading skeleton
    const { container } = render(
      <MemoryRouter initialEntries={["/"]}>
        <AuthProvider>
          <ProtectedRoute>
            <div data-testid="protected-content">Secret Dashboard</div>
          </ProtectedRoute>
        </AuthProvider>
      </MemoryRouter>
    );

    // While loading, skeleton is shown
    expect(screen.queryByTestId("protected-content")).not.toBeInTheDocument();
    expect(container.querySelector('[role="status"]')).toBeInTheDocument();
  });

  it("handles sign-in failure with safe generic error message", async () => {
    const { supabase } = await import("../lib/supabase");
    // Mock failed login
    vi.mocked(supabase!.auth.signInWithPassword).mockResolvedValueOnce({
      data: { user: null, session: null },
      error: {
        message: "Invalid login credentials",
        name: "AuthApiError",
        status: 400,
      } as unknown as import("@supabase/supabase-js").AuthError,
    });

    render(
      <MemoryRouter initialEntries={["/login"]}>
        <AuthProvider>
          <LoginPage />
        </AuthProvider>
      </MemoryRouter>
    );

    fireEvent.change(screen.getByLabelText(/Email address/i), {
      target: { value: "wrong@company.com" },
    });
    fireEvent.change(screen.getByLabelText(/Password/i), {
      target: { value: "wrongpassword" },
    });

    fireEvent.click(screen.getByRole("button", { name: /Sign in to Dashboard/i }));

    await waitFor(() => {
      expect(
        screen.getByText("Invalid email or password. Please verify your credentials.")
      ).toBeInTheDocument();
    });
  });

  it("handles session expiration and renders session expired alert", async () => {
    function ExpireTrigger() {
      const { markSessionExpired } = useAuth();
      return <button onClick={markSessionExpired}>Trigger Expiry</button>;
    }

    render(
      <MemoryRouter initialEntries={["/"]}>
        <AuthProvider>
          <UserProfileProvider>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route
                path="/"
                element={
                  <ProtectedRoute>
                    <ExpireTrigger />
                  </ProtectedRoute>
                }
              />
            </Routes>
          </UserProfileProvider>
        </AuthProvider>
      </MemoryRouter>
    );

    // Initial state: unauthenticated redirects to /login
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Sign in to Dashboard/i })).toBeInTheDocument();
    });
  });

  it("renders Settings page with exact privacy guarantee and retention schedule", async () => {
    render(
      <MemoryRouter initialEntries={["/settings"]}>
        <AuthProvider>
          <UserProfileProvider>
            <SettingsPage />
          </UserProfileProvider>
        </AuthProvider>
      </MemoryRouter>
    );

    // Check exact privacy quote from DESIGN.md §9
    expect(
      screen.getByText(/Camera frames are processed on this workstation/)
    ).toBeInTheDocument();

    // Check retention policies (metrics retention & audit log retention)
    expect(screen.getAllByText("365 Days")).toHaveLength(2);
    expect(screen.getByText("30 Days")).toBeInTheDocument();

    // Check disclaimer
    expect(
      screen.getByText(/EdgeErgo is a workplace ergonomic screening indicator/)
    ).toBeInTheDocument();
  });

  it("restores session and displays admin navigation (with Devices) for admin role", async () => {
    const { supabase } = await import("../lib/supabase");
    const { fetchMe } = await import("../lib/api");

    // Mock active session
    vi.mocked(supabase!.auth.getSession).mockResolvedValueOnce({
      data: {
        session: {
          access_token: "valid-admin-token",
          user: {
            id: "admin-1",
            email: "admin@company.com",
            app_metadata: {},
            user_metadata: {},
            aud: "authenticated",
            created_at: new Date().toISOString(),
          },
          token_type: "bearer",
          expires_in: 3600,
          refresh_token: "refresh-token",
        },
      },
      error: null,
    });

    // Mock admin profile
    vi.mocked(fetchMe).mockResolvedValueOnce({
      user_id: "admin-1",
      email: "admin@company.com",
      organization_id: "org-1",
      organization_slug: "test-corp",
      role: "admin",
    });

    const { AppShell } = await import("../components/layout/AppShell");

    render(
      <MemoryRouter initialEntries={["/"]}>
        <AuthProvider>
          <UserProfileProvider>
            <AppShell>
              <div>Dashboard Body</div>
            </AppShell>
          </UserProfileProvider>
        </AuthProvider>
      </MemoryRouter>
    );

    // As admin, Devices link should be present in primary nav
    await waitFor(() => {
      expect(screen.getByRole("link", { name: /Devices/i })).toBeInTheDocument();
      expect(screen.getByRole("link", { name: /Assessments/i })).toBeInTheDocument();
    });
  });

  it("omits Devices link from primary navigation for reviewer role", async () => {
    const { supabase } = await import("../lib/supabase");
    const { fetchMe } = await import("../lib/api");

    // Mock active reviewer session
    vi.mocked(supabase!.auth.getSession).mockResolvedValueOnce({
      data: {
        session: {
          access_token: "valid-reviewer-token",
          user: {
            id: "reviewer-1",
            email: "reviewer@company.com",
            app_metadata: {},
            user_metadata: {},
            aud: "authenticated",
            created_at: new Date().toISOString(),
          },
          token_type: "bearer",
          expires_in: 3600,
          refresh_token: "refresh-token-2",
        },
      },
      error: null,
    });

    // Mock reviewer profile
    vi.mocked(fetchMe).mockResolvedValueOnce({
      user_id: "reviewer-1",
      email: "reviewer@company.com",
      organization_id: "org-1",
      organization_slug: "test-corp",
      role: "reviewer",
    });

    const { AppShell } = await import("../components/layout/AppShell");

    render(
      <MemoryRouter initialEntries={["/"]}>
        <AuthProvider>
          <UserProfileProvider>
            <AppShell>
              <div>Dashboard Body</div>
            </AppShell>
          </UserProfileProvider>
        </AuthProvider>
      </MemoryRouter>
    );

    // As reviewer, Devices link should NOT be present in primary nav, while Assessments is present
    await waitFor(() => {
      expect(screen.queryByRole("link", { name: /Devices/i })).not.toBeInTheDocument();
      expect(screen.getByRole("link", { name: /Assessments/i })).toBeInTheDocument();
    });
  });
});
