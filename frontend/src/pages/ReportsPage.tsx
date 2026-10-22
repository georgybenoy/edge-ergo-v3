import React, { useState, useMemo, useCallback } from "react";
import {
  FileSpreadsheet,
  Download,
  Filter,
  ShieldCheck,
} from "lucide-react";
import { PageHeader } from "../components/ui/PageHeader";
import { Card } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Select } from "../components/ui/Select";
import { DateRangeControl, DateRangePreset } from "../components/ui/DateRangeControl";
import { EmptyState } from "../components/ui/EmptyState";
import { ErrorState } from "../components/ui/ErrorState";
import { StaleDataBanner } from "../components/ui/StaleDataBanner";
import { useToast } from "../components/ui/Toast";
import { useAuth } from "../features/auth/AuthContext";
import { useUserProfile } from "../features/auth/UserProfileContext";
import { useDevFixture, MOCK_REPORT_PREVIEW, MOCK_DEVICES } from "../lib/devFixtures";
import {
  fetchReportPreview,
  fetchDevices,
  downloadAssessmentsCsv,
  triggerBlobDownload,
  ReportScopePreviewResponse,
  DeviceListItem,
} from "../lib/api";
import { useApiData } from "../lib/useApiData";

function getPresetDates(preset: DateRangePreset): { from_date: string; to_date: string } {
  const now = new Date();
  const to_date = now.toISOString();
  const start = new Date(now);

  if (preset === "today") {
    start.setUTCHours(0, 0, 0, 0);
  } else if (preset === "7d") {
    start.setDate(start.getDate() - 7);
  } else if (preset === "30d") {
    start.setDate(start.getDate() - 30);
  } else if (preset === "90d") {
    start.setDate(start.getDate() - 90);
  }

  return { from_date: start.toISOString(), to_date };
}

export const ReportsPage: React.FC = () => {
  const { accessToken } = useAuth();
  const { profile } = useUserProfile();
  const { isDevFixtureActive } = useDevFixture();
  const { showToast } = useToast();

  const [datePreset, setDatePreset] = useState<DateRangePreset>("30d");
  const [deviceId, setDeviceId] = useState<string>("");
  const [validity, setValidity] = useState<string>("");
  const [isDownloading, setIsDownloading] = useState<boolean>(false);

  const { from_date, to_date } = useMemo(() => getPresetDates(datePreset), [datePreset]);

  // Devices query for dropdown
  const devicesFetcher = useCallback(
    async (signal: AbortSignal): Promise<DeviceListItem[]> => {
      if (import.meta.env.DEV && isDevFixtureActive) return MOCK_DEVICES;
      if (!accessToken) return [];
      return fetchDevices(accessToken, signal);
    },
    [accessToken, isDevFixtureActive]
  );

  const { data: devices } = useApiData<DeviceListItem[]>({
    fetcher: devicesFetcher,
    enabled: Boolean(accessToken || (import.meta.env.DEV && isDevFixtureActive)),
    deps: [accessToken, isDevFixtureActive],
  });

  // Report Scope Preview Fetcher
  const previewFetcher = useCallback(
    async (signal: AbortSignal): Promise<ReportScopePreviewResponse> => {
      if (import.meta.env.DEV && isDevFixtureActive) return MOCK_REPORT_PREVIEW;
      if (!accessToken) throw new Error("Authentication required");
      return fetchReportPreview(
        accessToken,
        {
          device_id: deviceId || undefined,
          from_date,
          to_date,
          validity: validity || undefined,
        },
        signal
      );
    },
    [accessToken, deviceId, from_date, to_date, validity, isDevFixtureActive]
  );

  const {
    data: preview,
    loading: previewLoading,
    error: previewError,
    isStale,
    lastUpdated,
    refetch,
  } = useApiData<ReportScopePreviewResponse>({
    fetcher: previewFetcher,
    enabled: Boolean(accessToken || (import.meta.env.DEV && isDevFixtureActive)),
    deps: [previewFetcher],
  });

  // Handle Authenticated CSV Download
  const handleDownloadCsv = async () => {
    if (!accessToken && !(import.meta.env.DEV && isDevFixtureActive)) return;
    setIsDownloading(true);

    try {
      if (import.meta.env.DEV && isDevFixtureActive) {
        // Dev mode simulation
        const headers =
          "event_id,captured_at,scoring_method,scoring_version,validity,score,neck_score,trunk_score,upper_arm_score,guidance_codes,software_version\n";
        const rows =
          "e1111111,2026-10-18T10:00:00Z,rula_simplified,1.0.0,valid,3,2,2,1,NECK_FORWARD_FLEXION,3.2.0\n";
        const blob = new Blob([headers + rows], { type: "text/csv;charset=utf-8;" });
        const filename = `edgeergo_report_${new Date().toISOString().slice(0, 10)}.csv`;
        triggerBlobDownload(blob, filename);
      } else {
        const blob = await downloadAssessmentsCsv(accessToken!, {
          device_id: deviceId || undefined,
          from_date,
          to_date,
          validity: validity || undefined,
        });
        const filename = `edgeergo_report_${new Date().toISOString().slice(0, 10)}.csv`;
        triggerBlobDownload(blob, filename);
      }

      showToast(
        `Export file downloaded successfully with ${preview?.total_matching ?? 0} observation records.`,
        "success"
      );
    } catch (err: unknown) {
      showToast((err as Error).message || "Unable to download CSV report dataset.", "error");
    } finally {
      setIsDownloading(false);
    }
  };

  const totalMatching = preview?.total_matching ?? 0;
  const isTruncated = preview ? preview.total_matching > preview.capped_count : false;

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-2 border-b border-border/50">
        <PageHeader
          title="Reports & Data Export"
          subtitle="Generate reproducible ergonomic summaries and download sanitized CSV assessment datasets."
        />

        <Button
          variant="primary"
          onClick={handleDownloadCsv}
          disabled={isDownloading || previewLoading || totalMatching === 0}
          icon={<Download className={`w-4 h-4 ${isDownloading ? "animate-bounce" : ""}`} />}
          aria-label="Download authenticated CSV dataset"
        >
          {isDownloading ? "Generating CSV..." : "Download CSV Dataset"}
        </Button>
      </div>

      {/* Filter Parameters Card */}
      <Card className="p-4 space-y-4">
        <div className="flex items-center justify-between text-xs font-semibold uppercase tracking-wider text-text-muted">
          <div className="flex items-center gap-1.5">
            <Filter className="w-3.5 h-3.5" />
            <span>Export Scope Parameters</span>
          </div>
          <span className="text-[11px] font-normal normal-case text-text-muted">
            Organization: <strong className="text-text-primary">{profile?.organization_id?.slice(0, 8)}...</strong>
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {/* Date range */}
          <div>
            <label className="block text-xs font-medium text-text-secondary mb-1">
              Time Horizon
            </label>
            <DateRangeControl value={datePreset} onChange={setDatePreset} />
          </div>

          {/* Device filter */}
          <div>
            <label htmlFor="report-device-select" className="block text-xs font-medium text-text-secondary mb-1">
              Workstation Target
            </label>
            <Select
              id="report-device-select"
              value={deviceId}
              onChange={(e) => setDeviceId(e.target.value)}
              options={[
                { value: "", label: "Entire Fleet (All Workstations)" },
                ...(devices?.map((d) => ({ value: d.id, label: `${d.label} (${d.public_id})` })) || []),
              ]}
            />
          </div>

          {/* Validity filter */}
          <div>
            <label htmlFor="report-validity-select" className="block text-xs font-medium text-text-secondary mb-1">
              Validity Filter
            </label>
            <Select
              id="report-validity-select"
              value={validity}
              onChange={(e) => setValidity(e.target.value)}
              options={[
                { value: "", label: "All Telemetry (Valid & Invalid)" },
                { value: "valid", label: "Valid Observations Only" },
                { value: "insufficient", label: "Insufficient Observations Only" },
                { value: "invalid", label: "Invalid Observations Only" },
              ]}
            />
          </div>
        </div>
      </Card>

      {/* Stale notification */}
      {isStale && !previewLoading && (
        <StaleDataBanner
          lastUpdated={lastUpdated}
          onRefresh={refetch}
        />
      )}

      {/* Error state */}
      {previewError && (
        <ErrorState
          title="Scope Preview Unavailable"
          message={previewError.message || "Failed to calculate report scope."}
          onRetry={refetch}
        />
      )}

      {/* Scope Preview Results */}
      {preview && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card className="space-y-2">
            <span className="text-xs text-text-muted font-medium uppercase tracking-wider block">
              Matching Records
            </span>
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-bold font-mono text-text-primary">
                {preview.total_matching.toLocaleString()}
              </span>
              <span className="text-xs text-text-muted">rows</span>
            </div>
            {isTruncated && (
              <p className="text-[11px] text-amber-300">
                ⚠️ Dataset exceeds export ceiling. Truncated to {preview.capped_count.toLocaleString()} rows.
              </p>
            )}
          </Card>

          <Card className="space-y-2">
            <span className="text-xs text-text-muted font-medium uppercase tracking-wider block">
              Validity Breakdown
            </span>
            <div className="space-y-1 text-xs">
              <div className="flex justify-between">
                <span className="text-text-muted">Valid Observations:</span>
                <span className="font-mono font-medium text-emerald-400">{preview.valid_count}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-text-muted">Insufficient Telemetry:</span>
                <span className="font-mono font-medium text-amber-400">{preview.insufficient_count}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-text-muted">Invalid Telemetry:</span>
                <span className="font-mono font-medium text-rose-400">{preview.invalid_count}</span>
              </div>
            </div>
          </Card>

          <Card className="space-y-2">
            <span className="text-xs text-text-muted font-medium uppercase tracking-wider block">
              Captured Boundaries
            </span>
            <div className="space-y-1 text-xs text-text-muted">
              <div>
                <span>Earliest: </span>
                <span className="font-mono text-text-secondary">
                  {preview.earliest_captured_at
                    ? new Date(preview.earliest_captured_at).toISOString().replace("T", " ").slice(0, 19)
                    : "None"}
                </span>
              </div>
              <div>
                <span>Latest: </span>
                <span className="font-mono text-text-secondary">
                  {preview.latest_captured_at
                    ? new Date(preview.latest_captured_at).toISOString().replace("T", " ").slice(0, 19)
                    : "None"}
                </span>
              </div>
            </div>
          </Card>
        </div>
      )}

      {/* Empty State */}
      {preview && preview.total_matching === 0 && (
        <EmptyState
          title="No Telemetry in Selected Scope"
          description="There are no observation records matching the selected date window and workstation filters. Broaden your filters to generate an export."
          icon={<FileSpreadsheet className="w-8 h-8 text-text-muted" />}
        />
      )}

      {/* Data Integrity & Treatment of Invalid Rows Explanation */}
      <Card className="p-5 space-y-3 bg-surface-raised/30 border-border/70">
        <div className="flex items-center gap-2 text-sm font-semibold text-text-primary">
          <ShieldCheck className="w-4 h-4 text-accent" />
          <span>Export Schema & Data Integrity Guarantees</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs text-text-secondary leading-relaxed">
          <div className="space-y-1.5 p-3 rounded bg-surface border border-border/50">
            <h4 className="font-semibold text-text-primary">Treatment of Invalid & Insufficient Rows</h4>
            <p className="text-text-muted text-[11px]">
              Observations marked as <code>invalid</code> or <code>insufficient</code> (due to occlusion, absent subject, or confidence shortfall) have <strong>empty/blank values</strong> in score columns (<code>score</code>, <code>neck_score</code>, <code>trunk_score</code>, <code>upper_arm_score</code>).
            </p>
            <p className="text-text-muted text-[11px]">
              This strictly prevents analytical distortion when computing means in third-party business intelligence tools (Excel, Python, R, Tableau).
            </p>
          </div>

          <div className="space-y-1.5 p-3 rounded bg-surface border border-border/50">
            <h4 className="font-semibold text-text-primary">Spreadsheet Formula Injection Defense</h4>
            <p className="text-text-muted text-[11px]">
              Every text field emitted by the hosted export endpoint is sanitized: leading characters such as <code>=</code>, <code>+</code>, <code>-</code>, or <code>@</code> are safely prefixed with a single quote (<code>'</code>).
            </p>
            <p className="text-text-muted text-[11px]">
              This completely eliminates formula execution vulnerabilities (CSV injection) when the report is opened in Microsoft Excel or LibreOffice Calc.
            </p>
          </div>
        </div>

        <div className="pt-2 border-t border-border/40 flex items-center justify-between text-xs text-text-muted">
          <span>Transport Security: Authenticated Bearer token streaming via HTTPS TLS 1.3</span>
          <span className="font-mono text-[11px]">RFC 4180 CSV Compliant</span>
        </div>
      </Card>
    </div>
  );
};
