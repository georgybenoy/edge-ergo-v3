import React, { useState, useMemo, useCallback, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import {
  Activity,
  Filter,
  Download,
  RotateCcw,
  ChevronLeft,
  ChevronRight,
  Info,
  X,
  ShieldCheck,
  AlertCircle,
} from "lucide-react";
import { PageHeader } from "../components/ui/PageHeader";
import { Table, Column } from "../components/ui/Table";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Select } from "../components/ui/Select";
import { DateRangeControl, DateRangePreset } from "../components/ui/DateRangeControl";
import { EmptyState } from "../components/ui/EmptyState";
import { ErrorState } from "../components/ui/ErrorState";
import { StaleDataBanner } from "../components/ui/StaleDataBanner";
import { useToast } from "../components/ui/Toast";
import { useAuth } from "../features/auth/AuthContext";
import { useDevFixture, MOCK_ASSESSMENTS, MOCK_DEVICES } from "../lib/devFixtures";
import {
  fetchAssessments,
  fetchDevices,
  downloadAssessmentsCsv,
  triggerBlobDownload,
  AssessmentListItem,
  DeviceListItem,
  AssessmentListResponse,
} from "../lib/api";
import { useApiData } from "../lib/useApiData";

const PAGE_SIZE = 25;

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

function getRulaCategoryLabel(score: number): string {
  if (score <= 2) return "Low Risk";
  if (score <= 4) return "Action Recommended";
  if (score <= 6) return "Investigation Required";
  return "Immediate Change";
}

function getRulaBadgeVariant(score: number): "success" | "warning" | "danger" {
  if (score <= 2) return "success";
  if (score <= 4) return "warning";
  return "danger";
}

export const AssessmentsPage: React.FC = () => {
  const { accessToken } = useAuth();
  const { isDevFixtureActive } = useDevFixture();
  const { showToast } = useToast();
  const [searchParams, setSearchParams] = useSearchParams();

  // Read URL query params
  const initialPreset = (searchParams.get("preset") as DateRangePreset) || "7d";
  const initialDevice = searchParams.get("device_id") || "";
  const initialValidity = searchParams.get("validity") || "";
  const initialScoringVersion = searchParams.get("scoring_version") || "";
  const initialPage = parseInt(searchParams.get("page") || "1", 10) || 1;

  const [datePreset, setDatePreset] = useState<DateRangePreset>(initialPreset);
  const [deviceId, setDeviceId] = useState<string>(initialDevice);
  const [validity, setValidity] = useState<string>(initialValidity);
  const [scoringVersion, setScoringVersion] = useState<string>(initialScoringVersion);
  const [page, setPage] = useState<number>(initialPage);

  const [selectedAssessment, setSelectedAssessment] = useState<AssessmentListItem | null>(null);
  const [isExporting, setIsExporting] = useState<boolean>(false);

  // Sync state to URL search params
  useEffect(() => {
    const params = new URLSearchParams();
    if (datePreset !== "7d") params.set("preset", datePreset);
    if (deviceId) params.set("device_id", deviceId);
    if (validity) params.set("validity", validity);
    if (scoringVersion) params.set("scoring_version", scoringVersion);
    if (page > 1) params.set("page", String(page));
    setSearchParams(params, { replace: true });
  }, [datePreset, deviceId, validity, scoringVersion, page, setSearchParams]);

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

  const deviceMap = useMemo(() => {
    const map = new Map<string, string>();
    if (devices) {
      devices.forEach((d) => map.set(d.id, d.label));
    }
    return map;
  }, [devices]);

  // Assessments list query
  const assessmentsFetcher = useCallback(
    async (signal: AbortSignal): Promise<AssessmentListResponse> => {
      if (import.meta.env.DEV && isDevFixtureActive) {
        return MOCK_ASSESSMENTS;
      }
      if (!accessToken) {
        throw new Error("Missing authentication token");
      }
      return fetchAssessments(
        accessToken,
        {
          device_id: deviceId || undefined,
          from_date,
          to_date,
          validity: validity || undefined,
          scoring_version: scoringVersion || undefined,
          limit: PAGE_SIZE,
          offset: (page - 1) * PAGE_SIZE,
        },
        signal
      );
    },
    [accessToken, deviceId, from_date, to_date, validity, scoringVersion, page, isDevFixtureActive]
  );

  const {
    data: assessmentsResponse,
    loading,
    error,
    isStale,
    lastUpdated,
    refetch,
  } = useApiData<AssessmentListResponse>({
    fetcher: assessmentsFetcher,
    enabled: Boolean(accessToken || (import.meta.env.DEV && isDevFixtureActive)),
    deps: [assessmentsFetcher],
  });

  const handleResetFilters = () => {
    setDatePreset("7d");
    setDeviceId("");
    setValidity("");
    setScoringVersion("");
    setPage(1);
  };

  const handleExportCsv = async () => {
    if (!accessToken && !(import.meta.env.DEV && isDevFixtureActive)) return;
    setIsExporting(true);
    try {
      if (import.meta.env.DEV && isDevFixtureActive) {
        // Dev mode simulated CSV
        const sampleCsv =
          "event_id,captured_at,scoring_method,scoring_version,validity,score\n" +
          MOCK_ASSESSMENTS.items
            .map(
              (i) =>
                `${i.event_id},${i.captured_at},${i.scoring_method},${i.scoring_version},${i.validity},${i.score || ""}`
            )
            .join("\n");
        const blob = new Blob([sampleCsv], { type: "text/csv;charset=utf-8;" });
        triggerBlobDownload(blob, `edgeergo_assessments_${new Date().toISOString().slice(0, 10)}.csv`);
      } else {
        const blob = await downloadAssessmentsCsv(accessToken!, {
          device_id: deviceId || undefined,
          from_date,
          to_date,
          validity: validity || undefined,
        });
        triggerBlobDownload(blob, `edgeergo_assessments_${new Date().toISOString().slice(0, 10)}.csv`);
      }
      showToast("Assessment records successfully downloaded with current filters applied.", "success");
    } catch (err: unknown) {
      showToast((err as Error).message || "Unable to download report CSV.", "error");
    } finally {
      setIsExporting(false);
    }
  };

  const totalCount = assessmentsResponse?.total || 0;
  const totalPages = Math.ceil(totalCount / PAGE_SIZE) || 1;
  const items = assessmentsResponse?.items || [];

  // Table Columns
  const columns: Column<AssessmentListItem>[] = [
    {
      key: "captured_at",
      header: "Timestamp (UTC)",
      className: "font-mono text-xs whitespace-nowrap",
      render: (item) => new Date(item.captured_at).toISOString().replace("T", " ").slice(0, 19),
    },
    {
      key: "device",
      header: "Device",
      render: (item) => (
        <span className="font-medium text-xs">
          {deviceMap.get(item.device_id) || `${item.device_id.slice(0, 8)}...`}
        </span>
      ),
    },
    {
      key: "validity",
      header: "Validity",
      render: (item) => {
        if (item.validity === "valid") {
          return <Badge variant="success" label="Valid" />;
        }
        if (item.validity === "insufficient") {
          return <Badge variant="warning" label="Insufficient" />;
        }
        return <Badge variant="danger" label="Invalid" />;
      },
    },
    {
      key: "scoring",
      header: "Method / Version",
      className: "text-xs font-mono text-text-muted",
      render: (item) => `${item.scoring_method} v${item.scoring_version}`,
    },
    {
      key: "score",
      header: "Posture Indicator",
      render: (item) => {
        // Enforce: invalid observations show why excluded and never a score
        if (item.validity !== "valid" || item.score === null) {
          return (
            <span className="text-xs text-text-muted italic">
              — (Excluded from scoring)
            </span>
          );
        }
        const numScore = Number(item.score);
        const badgeVariant = getRulaBadgeVariant(numScore);
        const category = getRulaCategoryLabel(numScore);
        return (
          <div className="flex items-center gap-1.5">
            <span className="font-mono font-semibold text-text-primary text-sm">
              RULA {item.score}
            </span>
            <Badge variant={badgeVariant} label={category} />
          </div>
        );
      },
    },
    {
      key: "guidance",
      header: "Guidance Flags",
      render: (item) => {
        if (!item.guidance_codes || item.guidance_codes.length === 0) {
          return <span className="text-xs text-text-muted">None</span>;
        }
        return (
          <div className="flex flex-wrap gap-1">
            {item.guidance_codes.map((code) => (
              <span
                key={code}
                className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-surface-muted text-amber-300 border border-border"
              >
                {code}
              </span>
            ))}
          </div>
        );
      },
    },
    {
      key: "actions",
      header: "Actions",
      className: "text-right",
      render: (item) => (
        <Button
          variant="outline"
          size="sm"
          onClick={() => setSelectedAssessment(item)}
          aria-label={`View details for assessment ${item.event_id}`}
        >
          Details
        </Button>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-2 border-b border-border/50">
        <PageHeader
          title="Assessment History"
          subtitle="Detailed logs of validated ergonomic screening events and practical guidance codes."
        />

        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            size="sm"
            onClick={handleExportCsv}
            disabled={isExporting || totalCount === 0}
            icon={<Download className={`w-3.5 h-3.5 ${isExporting ? "animate-pulse" : ""}`} />}
            aria-label="Export filtered assessments to CSV"
          >
            {isExporting ? "Exporting..." : "Export CSV"}
          </Button>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="p-4 rounded-panel bg-surface border border-border space-y-3">
        <div className="flex items-center justify-between gap-2 text-xs font-semibold uppercase tracking-wider text-text-muted">
          <div className="flex items-center gap-1.5">
            <Filter className="w-3.5 h-3.5" />
            <span>Filter Observations</span>
          </div>
          {(deviceId || validity || scoringVersion || datePreset !== "7d") && (
            <button
              onClick={handleResetFilters}
              className="flex items-center gap-1 text-accent hover:underline lowercase font-normal"
            >
              <RotateCcw className="w-3 h-3" />
              <span>reset filters</span>
            </button>
          )}
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {/* Date range filter */}
          <div>
            <label className="block text-xs text-text-muted mb-1 font-medium">Capture Period</label>
            <DateRangeControl
              value={datePreset}
              onChange={(p) => {
                setDatePreset(p);
                setPage(1);
              }}
            />
          </div>

          {/* Device filter */}
          <div>
            <label htmlFor="assessment-device-select" className="block text-xs text-text-muted mb-1 font-medium">Workstation</label>
            <Select
              id="assessment-device-select"
              value={deviceId}
              onChange={(e) => {
                setDeviceId(e.target.value);
                setPage(1);
              }}
              options={[
                { value: "", label: "All Workstations" },
                ...(devices?.map((d) => ({ value: d.id, label: `${d.label} (${d.public_id})` })) || []),
              ]}
            />
          </div>

          {/* Validity filter */}
          <div>
            <label htmlFor="assessment-validity-select" className="block text-xs text-text-muted mb-1 font-medium">Validity State</label>
            <Select
              id="assessment-validity-select"
              value={validity}
              onChange={(e) => {
                setValidity(e.target.value);
                setPage(1);
              }}
              options={[
                { value: "", label: "All Validity States" },
                { value: "valid", label: "Valid Only" },
                { value: "insufficient", label: "Insufficient Only" },
                { value: "invalid", label: "Invalid Only" },
              ]}
            />
          </div>

          {/* Scoring version filter */}
          <div>
            <label htmlFor="assessment-scoring-version-select" className="block text-xs text-text-muted mb-1 font-medium">Scoring Version</label>
            <Select
              id="assessment-scoring-version-select"
              value={scoringVersion}
              onChange={(e) => {
                setScoringVersion(e.target.value);
                setPage(1);
              }}
              options={[
                { value: "", label: "All Versions" },
                { value: "1.0.0", label: "v1.0.0 (Simplified RULA)" },
              ]}
            />
          </div>
        </div>
      </div>

      {/* Stale notification */}
      {isStale && !loading && (
        <StaleDataBanner
          lastUpdated={lastUpdated}
          onRefresh={refetch}
        />
      )}

      {/* Error state */}
      {error && (
        <ErrorState
          title="Failed to Load Assessments"
          message={error.message || "An error occurred fetching assessment records."}
          onRetry={refetch}
        />
      )}

      {/* Main Table */}
      <Table<AssessmentListItem>
        columns={columns}
        data={items}
        keyExtractor={(item) => item.event_id}
        loading={loading && items.length === 0}
        emptyState={
          <EmptyState
            title="No Assessments Found"
            description="No assessment records match the selected date range and filter criteria. Try expanding the date range or resetting filters."
            icon={<Activity className="w-8 h-8 text-text-muted" />}
          />
        }
      />

      {/* Pagination Footer */}
      {totalCount > 0 && (
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-2 text-xs text-text-muted">
          <div>
            Showing{" "}
            <span className="font-medium text-text-primary">
              {(page - 1) * PAGE_SIZE + 1}
            </span>{" "}
            to{" "}
            <span className="font-medium text-text-primary">
              {Math.min(page * PAGE_SIZE, totalCount)}
            </span>{" "}
            of{" "}
            <span className="font-medium text-text-primary">
              {totalCount.toLocaleString()}
            </span>{" "}
            total observations
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage((p) => Math.max(p - 1, 1))}
              disabled={page <= 1 || loading}
              icon={<ChevronLeft className="w-3.5 h-3.5" />}
              aria-label="Previous page"
            >
              Previous
            </Button>
            <span className="font-mono px-2">
              Page {page} of {totalPages}
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage((p) => Math.min(p + 1, totalPages))}
              disabled={page >= totalPages || loading}
              icon={<ChevronRight className="w-3.5 h-3.5" />}
              aria-label="Next page"
            >
              Next
            </Button>
          </div>
        </div>
      )}

      {/* Detail Drawer Modal */}
      {selectedAssessment && (
        <div
          className="fixed inset-0 z-50 overflow-hidden bg-black/60 backdrop-blur-xs flex justify-end"
          role="dialog"
          aria-modal="true"
          aria-labelledby="drawer-title"
        >
          <div className="w-full max-w-lg bg-surface border-l border-border h-full overflow-y-auto p-6 flex flex-col justify-between shadow-2xl">
            <div className="space-y-6">
              {/* Drawer Header */}
              <div className="flex items-start justify-between gap-4 pb-4 border-b border-border">
                <div>
                  <h2 id="drawer-title" className="text-base font-semibold text-text-primary">
                    Assessment Telemetry Details
                  </h2>
                  <p className="text-xs font-mono text-text-muted mt-0.5">
                    ID: {selectedAssessment.event_id}
                  </p>
                </div>
                <button
                  onClick={() => setSelectedAssessment(null)}
                  className="p-1 rounded hover:bg-surface-raised text-text-muted hover:text-text-primary transition-colors focus:outline-none focus:ring-2 focus:ring-accent"
                  aria-label="Close telemetry details drawer"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* Validity Section */}
              <div className="p-4 rounded bg-surface-muted border border-border/80 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-text-muted uppercase tracking-wider">
                    Observation Validity
                  </span>
                  {selectedAssessment.validity === "valid" ? (
                    <Badge variant="success" label="Valid Telemetry" />
                  ) : selectedAssessment.validity === "insufficient" ? (
                    <Badge variant="warning" label="Insufficient Observation" />
                  ) : (
                    <Badge variant="danger" label="Invalid Observation" />
                  )}
                </div>

                <p className="text-xs text-text-secondary leading-relaxed">
                  {selectedAssessment.validity === "valid"
                    ? "Upper-body keypoint detector satisfied all anatomical confidence thresholds (> 0.50). Posture calculation was computed successfully on the edge device."
                    : selectedAssessment.validity === "insufficient"
                    ? "Joint visibility was partially occluded or below confidence threshold. Excluded from ergonomic index scoring to protect measurement integrity."
                    : "Subject was absent, out of frame, or extreme occlusion occurred. Excluded from ergonomic scoring."}
                </p>

                {selectedAssessment.validity !== "valid" && (
                  <div className="flex items-center gap-2 text-xs text-amber-300 font-medium pt-1">
                    <AlertCircle className="w-4 h-4 shrink-0" />
                    <span>Score Excluded: Non-valid observations never carry an ergonomic score.</span>
                  </div>
                )}
              </div>

              {/* Approved Posture Factor Features */}
              <div className="space-y-3">
                <div className="flex items-center justify-between border-b border-border/50 pb-1">
                  <h3 className="text-sm font-semibold text-text-primary">
                    Approved Anatomical Joint Angles
                  </h3>
                  <Badge variant="neutral" label="Privacy Verified" />
                </div>

                {selectedAssessment.validity === "valid" ? (
                  <div className="grid grid-cols-3 gap-3">
                    <div className="p-3 rounded bg-surface-raised border border-border text-center">
                      <span className="text-[11px] text-text-muted block">Neck Score</span>
                      <span className="text-xl font-bold font-mono text-text-primary mt-1 block">
                        {selectedAssessment.neck_score ?? "—"}
                      </span>
                      <span className="text-[10px] text-text-muted">Flexion &le; 20°</span>
                    </div>

                    <div className="p-3 rounded bg-surface-raised border border-border text-center">
                      <span className="text-[11px] text-text-muted block">Trunk Score</span>
                      <span className="text-xl font-bold font-mono text-text-primary mt-1 block">
                        {selectedAssessment.trunk_score ?? "—"}
                      </span>
                      <span className="text-[10px] text-text-muted">Upright &le; 20°</span>
                    </div>

                    <div className="p-3 rounded bg-surface-raised border border-border text-center">
                      <span className="text-[11px] text-text-muted block">Upper Arm</span>
                      <span className="text-xl font-bold font-mono text-text-primary mt-1 block">
                        {selectedAssessment.upper_arm_score ?? "—"}
                      </span>
                      <span className="text-[10px] text-text-muted">Elevation &le; 45°</span>
                    </div>
                  </div>
                ) : (
                  <p className="text-xs text-text-muted italic">
                    Anatomical joint scores are not computed for invalid or insufficient observations.
                  </p>
                )}

                <div className="p-3 bg-surface-raised/40 rounded border border-border/60 text-[11px] text-text-muted space-y-1">
                  <div className="flex items-center gap-1.5 font-medium text-text-secondary">
                    <ShieldCheck className="w-3.5 h-3.5 text-accent" />
                    <span>Zero Raw Media Ingestion</span>
                  </div>
                  <p>
                    EdgeErgo V3 processes webcam frames ephemerally on the workstation CPU/NPU. Only aggregate scalar joint scores and guidance codes are transmitted to the host. No video, raw frames, or 33 coordinate landmark meshes are ever stored.
                  </p>
                </div>
              </div>

              {/* Guidance Recommendations */}
              <div className="space-y-3">
                <h3 className="text-sm font-semibold text-text-primary border-b border-border/50 pb-1">
                  Practical Guidance & Corrective Indicators
                </h3>

                {selectedAssessment.guidance_codes && selectedAssessment.guidance_codes.length > 0 ? (
                  <div className="space-y-2">
                    {selectedAssessment.guidance_codes.map((code) => (
                      <div
                        key={code}
                        className="p-3 rounded bg-surface-muted border border-border text-xs space-y-1"
                      >
                        <span className="font-mono font-semibold text-amber-300">{code}</span>
                        <p className="text-text-muted">
                          {code === "NECK_FORWARD_FLEXION"
                            ? "Elevate display to eye level to avoid cervical spine flexion."
                            : code === "TRUNK_TWISTED"
                            ? "Re-center keyboard and display directly in front of body."
                            : code === "UPPER_ARM_ELEVATION"
                            ? "Lower desk or adjust armrests to relax upper shoulder muscles."
                            : "Adjust workstation setup to maintain neutral joint alignment."}
                        </p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-text-muted">
                    No posture risk flags were triggered for this observation window.
                  </p>
                )}
              </div>
            </div>

            {/* Mandatory Screening Disclaimer in Drawer */}
            <div className="pt-6 border-t border-border space-y-3">
              <div className="p-3 rounded bg-surface-raised/60 border border-border text-[11px] text-text-muted flex items-start gap-2">
                <Info className="w-4 h-4 shrink-0 text-accent mt-0.5" />
                <p>
                  <strong>Notice:</strong> Screening indicator and practical guide only; not a medical diagnostic tool or employee evaluation system.
                </p>
              </div>

              <Button
                variant="outline"
                className="w-full"
                onClick={() => setSelectedAssessment(null)}
              >
                Close Details
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
