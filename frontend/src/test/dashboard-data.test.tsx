import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { OverviewPage } from "../pages/OverviewPage";
import { AssessmentsPage } from "../pages/AssessmentsPage";
import { DevicesPage } from "../pages/DevicesPage";
import { ReportsPage } from "../pages/ReportsPage";
import { AuthProvider } from "../features/auth/AuthContext";
import { UserProfileProvider } from "../features/auth/UserProfileContext";
import { ToastProvider } from "../components/ui/Toast";
import {
  MOCK_DASHBOARD_SUMMARY,
  MOCK_DEVICES,
  MOCK_ASSESSMENTS,
  MOCK_REPORT_PREVIEW,
} from "../lib/devFixtureData";
import * as api from "../lib/api";
import { supabase } from "../lib/supabase";

// Mock Supabase
vi.mock("../lib/supabase", () => ({
  getMissingEnvConfig: () => [],
  supabase: {
    auth: {
      getSession: vi.fn(),
      onAuthStateChange: vi.fn(() => ({
        data: { subscription: { unsubscribe: vi.fn() } },
      })),
      signOut: vi.fn().mockResolvedValue({ error: null }),
    },
  },
}));

describe("Phase 5 — Dashboard Data & Real API Contracts", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    vi.mocked(supabase!.auth.getSession).mockResolvedValue({
      data: {
        session: {
          access_token: "mock_jwt_token_123",
          token_type: "bearer",
          expires_in: 3600,
          refresh_token: "mock-refresh-token",
          user: {
            id: "u_test_123",
            email: "admin@corp.com",
            app_metadata: {},
            user_metadata: {},
            aud: "authenticated",
            created_at: new Date().toISOString(),
          },
        },
      },
      error: null,
    });

    // Default mock API implementations
    vi.spyOn(api, "fetchMe").mockResolvedValue({
      user_id: "u_test_123",
      email: "admin@corp.com",
      organization_id: "org_test_123",
      organization_slug: "test-org",
      role: "admin",
    });

    vi.spyOn(api, "fetchDashboardSummary").mockResolvedValue(MOCK_DASHBOARD_SUMMARY);
    vi.spyOn(api, "fetchDevices").mockResolvedValue(MOCK_DEVICES);
    vi.spyOn(api, "fetchAssessments").mockResolvedValue(MOCK_ASSESSMENTS);
    vi.spyOn(api, "fetchReportPreview").mockResolvedValue(MOCK_REPORT_PREVIEW);
  });

  const renderWithProviders = (ui: React.ReactElement, initialRoute = "/") => {
    return render(
      <MemoryRouter initialEntries={[initialRoute]}>
        <AuthProvider>
          <UserProfileProvider>
            <ToastProvider>
              <Routes>
                <Route path="/" element={ui} />
                <Route path="/assessments" element={ui} />
                <Route path="/devices" element={ui} />
                <Route path="/reports" element={ui} />
              </Routes>
            </ToastProvider>
          </UserProfileProvider>
        </AuthProvider>
      </MemoryRouter>
    );
  };

  describe("Overview Page", () => {
    it("renders real KPI cards with definitions and sample counts", async () => {
      renderWithProviders(<OverviewPage />);

      // Verify KPI values
      await waitFor(() => {
        expect(screen.getByText("142")).toBeInTheDocument(); // Assessments Recorded
        expect(screen.getByText("3.4")).toBeInTheDocument(); // Average RULA
        expect(screen.getByText("4 / 5")).toBeInTheDocument(); // Workstations Reporting
        expect(screen.getByText("Up to date")).toBeInTheDocument(); // Sync Status
      });

      // Verify KPI definition and sample counts
      expect(
        screen.getByText(/Mean partial RULA screening risk score across valid upper-body observations/i)
      ).toBeInTheDocument();
      expect(screen.getByText(/Sample size: 130 observations/i)).toBeInTheDocument();
      expect(
        screen.getByText(/Total valid and invalid assessment observation events/i)
      ).toBeInTheDocument();
    });

    it("handles 'Not enough data' path when scoring is heterogeneous or lacks valid samples", async () => {
      vi.spyOn(api, "fetchDashboardSummary").mockResolvedValueOnce({
        ...MOCK_DASHBOARD_SUMMARY,
        average_rula_score: {
          name: "Average Ergonomic Indicator",
          value: null,
          sample_count: 0,
          definition: "Mean partial RULA score",
          reason: "Multiple incompatible scoring algorithms detected in query window.",
        },
      });

      renderWithProviders(<OverviewPage />);

      await waitFor(() => {
        expect(screen.getByText("Not enough data")).toBeInTheDocument();
        expect(
          screen.getByText("Multiple incompatible scoring algorithms detected in query window.")
        ).toBeInTheDocument();
      });
    });

    it("renders Recharts assessment trend accessible text summary and data table alternative toggle", async () => {
      renderWithProviders(<OverviewPage />);

      // Verify chart accessible text summary
      await waitFor(() => {
        expect(screen.getByText(/Trend Summary:/i)).toBeInTheDocument();
      });
      expect(screen.getByText(/Across 6 calendar days in the window, 6 days had valid posture telemetry/i)).toBeInTheDocument();

      // Toggle to accessible data table
      const tableToggleBtn = screen.getByRole("button", { name: /switch to accessible data table/i });
      fireEvent.click(tableToggleBtn);

      expect(screen.getByText("Assessment Daily Trend Data Table")).toBeInTheDocument();
      expect(screen.getByText("2026-10-14")).toBeInTheDocument();
      expect(screen.getByText("3.8")).toBeInTheDocument();

      // Toggle back to chart
      const chartToggleBtn = screen.getByRole("button", { name: /switch to trend line chart/i });
      fireEvent.click(chartToggleBtn);
      expect(screen.queryByText("Assessment Daily Trend Data Table")).not.toBeInTheDocument();
    });

    it("displays device status summary with the precise 450s online definition", async () => {
      renderWithProviders(<OverviewPage />);

      await waitFor(() => {
        expect(screen.getByText("Workstation Connectivity")).toBeInTheDocument();
        expect(screen.getByText(/450 seconds/i)).toBeInTheDocument();
        expect(screen.getByText(/never implies live camera access or audio feed/i)).toBeInTheDocument();
      });
    });

    it("filters summary data when workstation is selected", async () => {
      const summarySpy = vi.spyOn(api, "fetchDashboardSummary");
      renderWithProviders(<OverviewPage />);

      await waitFor(() => {
        expect(screen.getByText("Workstation Alpha (Design Dept) (eed_pub_alpha12345)")).toBeInTheDocument();
      });

      const select = screen.getByRole("combobox");
      fireEvent.change(select, { target: { value: "d1111111-1111-1111-1111-111111111111" } });

      await waitFor(() => {
        expect(summarySpy).toHaveBeenCalledWith(
          "mock_jwt_token_123",
          expect.objectContaining({
            device_id: "d1111111-1111-1111-1111-111111111111",
          }),
          expect.any(AbortSignal)
        );
      });
    });
  });

  describe("Assessments Page", () => {
    it("renders assessments table and never renders score for invalid/insufficient observations", async () => {
      renderWithProviders(<AssessmentsPage />, "/assessments");

      await waitFor(() => {
        expect(screen.getByText("Assessment History")).toBeInTheDocument();
        expect(screen.getAllByText("RULA 3").length).toBeGreaterThan(0);
        expect(screen.getAllByText("RULA 4").length).toBeGreaterThan(0);
      });

      // Observations with invalid/insufficient status must say "— (Excluded from scoring)" and NEVER show a score
      const excludedElements = screen.getAllByText("— (Excluded from scoring)");
      expect(excludedElements.length).toBeGreaterThanOrEqual(2);
    });

    it("opens assessment detail drawer with screening indicator disclaimer and approved joint features", async () => {
      renderWithProviders(<AssessmentsPage />, "/assessments");

      await waitFor(() => {
        expect(screen.getAllByRole("button", { name: /view details for assessment/i })[0]).toBeInTheDocument();
      });

      // Click details on first valid assessment
      const detailsBtns = screen.getAllByRole("button", { name: /view details for assessment/i });
      const detailsBtn = detailsBtns[0]!;
      fireEvent.click(detailsBtn);

      await waitFor(() => {
        expect(screen.getByText("Assessment Telemetry Details")).toBeInTheDocument();
        expect(screen.getByText("Approved Anatomical Joint Angles")).toBeInTheDocument();
        expect(screen.getByText("Zero Raw Media Ingestion")).toBeInTheDocument();
        expect(
          screen.getByText(/Screening indicator and practical guide only; not a medical diagnostic tool/i)
        ).toBeInTheDocument();
      });

      // Close drawer
      const closeBtn = screen.getByRole("button", { name: /close details/i });
      fireEvent.click(closeBtn);
      expect(screen.queryByText("Assessment Telemetry Details")).not.toBeInTheDocument();
    });

    it("re-uses active filters when triggering CSV export", async () => {
      const exportSpy = vi.spyOn(api, "downloadAssessmentsCsv").mockResolvedValueOnce(
        new Blob(["col1,col2\nval1,val2"], { type: "text/csv" })
      );

      renderWithProviders(<AssessmentsPage />, "/assessments");

      await waitFor(() => {
        expect(screen.getByRole("button", { name: /export filtered assessments to csv/i })).toBeInTheDocument();
      });

      // Change validity filter to valid
      const validitySelect = screen.getByLabelText(/validity state/i);
      fireEvent.change(validitySelect, { target: { value: "valid" } });

      const exportBtn = screen.getByRole("button", { name: /export filtered assessments to csv/i });
      fireEvent.click(exportBtn);

      await waitFor(() => {
        expect(exportSpy).toHaveBeenCalledWith(
          "mock_jwt_token_123",
          expect.objectContaining({
            validity: "valid",
          })
        );
      });
    });
  });

  describe("Devices Page", () => {
    it("renders safe status badges, pending queue counts, and live camera disclaimer", async () => {
      renderWithProviders(<DevicesPage />, "/devices");

      await waitFor(() => {
        expect(screen.getAllByText("Workstation Alpha (Design Dept)").length).toBeGreaterThan(0);
        expect(screen.getAllByText("● Online").length).toBeGreaterThan(0);
        expect(screen.getAllByText("○ Offline").length).toBeGreaterThan(0);
        expect(screen.getAllByText("✕ Revoked").length).toBeGreaterThan(0);
        expect(screen.getAllByText("14 batches").length).toBeGreaterThan(0); // pending queue count
        expect(screen.getByText(/Device status NEVER implies live camera access/i)).toBeInTheDocument();
      });
    });

    it("shows enrollment token exactly once and clears it immediately upon dismissal", async () => {
      vi.spyOn(api, "createEnrollmentToken").mockResolvedValueOnce({
        token: "eet_secret_plaintext_token_xyz999",
        expires_at: new Date(Date.now() + 3600000).toISOString(),
        label: "New Workstation",
      });

      renderWithProviders(<DevicesPage />, "/devices");

      await waitFor(() => {
        expect(screen.getByRole("button", { name: /enroll workstation/i })).toBeInTheDocument();
      });

      // Open enrollment modal
      fireEvent.click(screen.getByRole("button", { name: /enroll workstation/i }));
      expect(screen.getByText("Generate Workstation Enrollment Token")).toBeInTheDocument();

      // Submit form
      const labelInput = screen.getByLabelText(/workstation label/i);
      fireEvent.change(labelInput, { target: { value: "New Workstation" } });
      fireEvent.click(screen.getByRole("button", { name: /generate token/i }));

      // Token displayed once
      await waitFor(() => {
        expect(screen.getByText("Single-Use Enrollment Token")).toBeInTheDocument();
        expect(screen.getByText("eet_secret_plaintext_token_xyz999")).toBeInTheDocument();
        expect(screen.getByText(/Show Once Guarantee:/i)).toBeInTheDocument();
      });

      // Dismiss modal
      fireEvent.click(screen.getByRole("button", { name: /i have saved the token/i }));

      // Assert token is completely cleared from DOM and state
      expect(screen.queryByText("eet_secret_plaintext_token_xyz999")).not.toBeInTheDocument();
      expect(screen.queryByText("Single-Use Enrollment Token")).not.toBeInTheDocument();
    });

    it("requires confirmation dialog before revoking a workstation credential", async () => {
      const revokeSpy = vi.spyOn(api, "revokeDevice").mockResolvedValueOnce({
        device_id: "d1111111-1111-1111-1111-111111111111",
        status: "revoked",
        revoked_at: new Date().toISOString(),
      });

      renderWithProviders(<DevicesPage />, "/devices");

      await waitFor(() => {
        expect(screen.getAllByRole("button", { name: /revoke credentials for workstation alpha/i })[0]).toBeInTheDocument();
      });

      // Click revoke
      const revokeBtns = screen.getAllByRole("button", { name: /revoke credentials for workstation alpha/i });
      fireEvent.click(revokeBtns[0]!);

      // Confirm dialog appears
      expect(screen.getByText("Revoke Workstation Credential?")).toBeInTheDocument();
      expect(screen.getByText(/permanently barred from submitting telemetry/i)).toBeInTheDocument();

      // Cancel button dismisses without calling API
      fireEvent.click(screen.getByRole("button", { name: /cancel/i }));
      expect(revokeSpy).not.toHaveBeenCalled();

      // Open again and confirm
      const revokeBtnsAfter = screen.getAllByRole("button", { name: /revoke credentials for workstation alpha/i });
      fireEvent.click(revokeBtnsAfter[0]!);
      fireEvent.click(screen.getByRole("button", { name: "Revoke Workstation" }));

      await waitFor(() => {
        expect(revokeSpy).toHaveBeenCalledWith("mock_jwt_token_123", "d1111111-1111-1111-1111-111111111111");
      });
    });

    it("restricts admin actions when user has reviewer role", async () => {
      vi.spyOn(api, "fetchMe").mockResolvedValueOnce({
        user_id: "u_reviewer_456",
        email: "reviewer@corp.com",
        organization_id: "org_test_123",
        organization_slug: "test-org",
        role: "reviewer",
      });

      renderWithProviders(<DevicesPage />, "/devices");

      await waitFor(() => {
        expect(screen.getByText(/Reviewer Mode: Device controls are read-only/i)).toBeInTheDocument();
      });

      // Enroll Workstation button is disabled for reviewer
      const enrollBtn = screen.getByRole("button", { name: /enroll workstation/i });
      expect(enrollBtn).toBeDisabled();

      // Action column displays "Read-only" instead of Revoke button
      expect(screen.queryByRole("button", { name: /revoke credentials for workstation alpha/i })).not.toBeInTheDocument();
      expect(screen.getAllByText("Read-only").length).toBeGreaterThan(0);
    });
  });

  describe("Reports Page", () => {
    it("renders scope preview with matching count and invalid row explanation", async () => {
      renderWithProviders(<ReportsPage />, "/reports");

      await waitFor(() => {
        expect(screen.getByText("Reports & Data Export")).toBeInTheDocument();
        expect(screen.getByText("142")).toBeInTheDocument(); // Matching records
        expect(screen.getByText("Valid Observations:")).toBeInTheDocument();
        expect(screen.getByText("130")).toBeInTheDocument();
        expect(screen.getByText(/Treatment of Invalid & Insufficient Rows/i)).toBeInTheDocument();
        expect(screen.getByText(/Spreadsheet Formula Injection Defense/i)).toBeInTheDocument();
      });
    });

    it("renders empty state and disables download button when matching count is 0", async () => {
      vi.spyOn(api, "fetchReportPreview").mockResolvedValueOnce({
        total_matching: 0,
        capped_count: 0,
        max_export_limit: 50000,
        valid_count: 0,
        invalid_count: 0,
        insufficient_count: 0,
        earliest_captured_at: null,
        latest_captured_at: null,
      });

      renderWithProviders(<ReportsPage />, "/reports");

      await waitFor(() => {
        expect(screen.getByText("No Telemetry in Selected Scope")).toBeInTheDocument();
        const downloadBtn = screen.getByRole("button", { name: /download authenticated csv dataset/i });
        expect(downloadBtn).toBeDisabled();
      });
    });
  });
});
