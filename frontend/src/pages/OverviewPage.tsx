import React, { useState, useMemo, useCallback } from "react";
import { Link } from "react-router-dom";
import {
  Activity,
  Layers,
  Laptop,
  RefreshCw,
  Clock,
  Table as TableIcon,
  LineChart as ChartIcon,
  ArrowRight,
  Info,
  CheckCircle2,
  AlertTriangle,
} from "lucide-react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";
import { PageHeader } from "../components/ui/PageHeader";
import { KpiCard } from "../components/ui/KpiCard";
import { Card } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Select } from "../components/ui/Select";
import { DateRangeControl, DateRangePreset } from "../components/ui/DateRangeControl";
import { Skeleton } from "../components/ui/Skeleton";
import { EmptyState } from "../components/ui/EmptyState";
import { ErrorState } from "../components/ui/ErrorState";
import { StaleDataBanner } from "../components/ui/StaleDataBanner";
import { useAuth } from "../features/auth/AuthContext";
import { useUserProfile } from "../features/auth/UserProfileContext";
import { useDevFixture, MOCK_DASHBOARD_SUMMARY, MOCK_DEVICES, MOCK_ASSESSMENTS } from "../lib/devFixtures";
import {
  fetchDashboardSummary,
  fetchDevices,
  fetchAssessments,
  DashboardSummaryResponse,
  DeviceListItem,
  AssessmentListItem,
  DashboardTrendPoint,
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

export const OverviewPage: React.FC = () => {
  const { accessToken } = useAuth();
  const { profile } = useUserProfile();
  const { isDevFixtureActive } = useDevFixture();

  const [datePreset, setDatePreset] = useState<DateRangePreset>("7d");
  const [selectedDeviceId, setSelectedDeviceId] = useState<string>("");
  const [showTableAlternative, setShowTableAlternative] = useState<boolean>(false);

  const { from_date, to_date } = useMemo(() => getPresetDates(datePreset), [datePreset]);

  // Devices query for dropdown filter
  const devicesFetcher = useCallback(
    async (signal: AbortSignal): Promise<DeviceListItem[]> => {
      if (import.meta.env.DEV && isDevFixtureActive) {
        return MOCK_DEVICES;
      }
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

  // Dashboard summary data fetcher
  const dashboardFetcher = useCallback(
    async (signal: AbortSignal): Promise<DashboardSummaryResponse> => {
      if (import.meta.env.DEV && isDevFixtureActive) {
        return MOCK_DASHBOARD_SUMMARY;
      }
      if (!accessToken) {
        throw new Error("Missing authentication token");
      }
      return fetchDashboardSummary(
        accessToken,
        {
          device_id: selectedDeviceId || undefined,
          from_date,
          to_date,
        },
        signal
      );
    },
    [accessToken, selectedDeviceId, from_date, to_date, isDevFixtureActive]
  );

  const {
    data: summary,
    loading,
    error,
    isStale,
    lastUpdated,
    refetch,
  } = useApiData<DashboardSummaryResponse>({
    fetcher: dashboardFetcher,
    enabled: Boolean(accessToken || (import.meta.env.DEV && isDevFixtureActive)),
    deps: [dashboardFetcher],
  });

  // Recent assessments for preview
  const recentAssessmentsFetcher = useCallback(
    async (signal: AbortSignal): Promise<AssessmentListItem[]> => {
      if (import.meta.env.DEV && isDevFixtureActive) {
        return MOCK_ASSESSMENTS.items.slice(0, 5);
      }
      if (!accessToken) return [];
      const res = await fetchAssessments(
        accessToken,
        {
          device_id: selectedDeviceId || undefined,
          limit: 5,
        },
        signal
      );
      return res.items;
    },
    [accessToken, selectedDeviceId, isDevFixtureActive]
  );

  const { data: recentAssessments } = useApiData<AssessmentListItem[]>({
    fetcher: recentAssessmentsFetcher,
    enabled: Boolean(accessToken || (import.meta.env.DEV && isDevFixtureActive)),
    deps: [recentAssessmentsFetcher],
  });

  const deviceOptions = useMemo(() => {
    const list = [{ value: "", label: "All Workstations" }];
    if (devices) {
      devices.forEach((d) => {
        list.push({ value: d.id, label: `${d.label} (${d.public_id})` });
      });
    }
    return list;
  }, [devices]);

  // Derived trend statistics for accessible summary
  const trendPoints: DashboardTrendPoint[] = useMemo(
    () => summary?.daily_trend || [],
    [summary?.daily_trend]
  );

  const trendValidPoints = useMemo(
    () => trendPoints.filter((p) => p.average_score !== null && p.average_score !== undefined),
    [trendPoints]
  );

  const trendStats = useMemo(() => {
    if (trendValidPoints.length === 0) return null;
    const scores = trendValidPoints.map((p) => p.average_score as number);
    const min = Math.min(...scores);
    const max = Math.max(...scores);
    const totalObservations = trendPoints.reduce(
      (acc, p) => acc + p.valid_count + p.insufficient_count + p.invalid_count,
      0
    );
    return {
      validDays: trendValidPoints.length,
      totalDays: trendPoints.length,
      minScore: min.toFixed(1),
      maxScore: max.toFixed(1),
      totalObservations,
    };
  }, [trendPoints, trendValidPoints]);

  return (
    <div className="space-y-6">
      {/* Header with live status, date range and device filters */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-2 border-b border-border/50">
        <div>
          <PageHeader
            title="Ergonomics Overview"
            subtitle="Real-time telemetry indicators and organizational posture screening trends."
          />
          <div className="flex flex-wrap items-center gap-3 mt-2 text-xs text-text-muted">
            <span className="flex items-center gap-1.5 font-medium text-emerald-400">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              Connected to Live Service
            </span>
            <span>&bull;</span>
            <span className="flex items-center gap-1">
              <Clock className="w-3.5 h-3.5" />
              Last updated: {lastUpdated ? lastUpdated.toLocaleTimeString() : "Synchronizing..."}
            </span>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <DateRangeControl value={datePreset} onChange={setDatePreset} />

          {deviceOptions.length > 1 && (
            <div className="w-44 sm:w-56">
              <Select
                id="overview-device-filter"
                value={selectedDeviceId}
                onChange={(e) => setSelectedDeviceId(e.target.value)}
                options={deviceOptions}
              />
            </div>
          )}

          <Button
            variant="outline"
            size="sm"
            onClick={() => refetch()}
            disabled={loading}
            aria-label="Refresh overview telemetry"
            icon={<RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />}
          >
            Refresh
          </Button>
        </div>
      </div>

      {/* Stale Data Notification */}
      {isStale && !loading && (
        <StaleDataBanner
          lastUpdated={lastUpdated}
          onRefresh={refetch}
        />
      )}

      {/* Error State */}
      {error && (
        <ErrorState
          title="Telemetry Ingestion Unavailable"
          message={error.message || "Unable to fetch aggregated overview telemetry from the server."}
          onRetry={refetch}
        />
      )}

      {/* Loading Skeletons */}
      {loading && !summary && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <Skeleton className="h-36 rounded-panel" />
            <Skeleton className="h-36 rounded-panel" />
            <Skeleton className="h-36 rounded-panel" />
            <Skeleton className="h-36 rounded-panel" />
          </div>
          <Skeleton className="h-80 rounded-panel" />
        </div>
      )}

      {/* Main KPI and Chart Section */}
      {summary && (
        <>
          {/* KPI Cards Row */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* 1. Assessments Recorded */}
            <KpiCard
              label="Assessments Recorded"
              value={summary.total_assessments}
              sampleCount={summary.total_assessments}
              definition="Total valid and invalid assessment observation events transmitted within the filter range."
              icon={<Activity className="w-4 h-4" />}
            />

            {/* 2. Average Ergonomic Indicator (RULA) */}
            <KpiCard
              label="Average Ergonomic Indicator"
              value={
                summary.average_rula_score.value !== null
                  ? summary.average_rula_score.value.toFixed(1)
                  : null
              }
              unit="RULA"
              insufficientReason={
                summary.average_rula_score.reason ||
                (summary.total_assessments === 0
                  ? "No telemetry recorded in selected window."
                  : "No valid scored assessments available.")
              }
              definition={summary.average_rula_score.definition}
              sampleCount={summary.average_rula_score.sample_count}
              icon={<Layers className="w-4 h-4" />}
            />

            {/* 3. Workstations Reporting */}
            <KpiCard
              label="Workstations Reporting"
              value={`${summary.online_devices_count} / ${summary.active_devices_count}`}
              definition="Number of enrolled workstations that transmitted at least one telemetry event within the period."
              icon={<Laptop className="w-4 h-4" />}
            />

            {/* 4. Sync Status */}
            <KpiCard
              label="Sync Status"
              value={summary.online_devices_count > 0 ? "Up to date" : "No Activity"}
              definition="Telemetry synchronization state between edge devices and the hosted ingestion service."
              icon={
                summary.online_devices_count > 0 ? (
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                ) : (
                  <AlertTriangle className="w-4 h-4 text-amber-400" />
                )
              }
            />
          </div>

          {/* Assessment Trend Section */}
          <Card className="space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-border/50">
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-base font-semibold text-text-primary">Assessment Trend</h2>
                  <Badge variant="neutral" label="Daily Average RULA (1–7)" />
                </div>
                <p className="text-xs text-text-muted mt-0.5">
                  Trajectory of daily mean posture scores for valid assessments. Missing periods are not interpolated.
                </p>
              </div>

              {trendPoints.length > 0 && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setShowTableAlternative((prev) => !prev)}
                  icon={showTableAlternative ? <ChartIcon className="w-3.5 h-3.5" /> : <TableIcon className="w-3.5 h-3.5" />}
                  aria-label={showTableAlternative ? "Switch to trend line chart" : "Switch to accessible data table"}
                >
                  {showTableAlternative ? "View Chart" : "View as Table"}
                </Button>
              )}
            </div>

            {trendPoints.length === 0 ? (
              <EmptyState
                title="No Trend Data Recorded"
                description="No assessment telemetry is available for the selected timeframe. As edge agents transmit valid assessment batches, daily trend metrics will populate automatically."
                icon={<Activity className="w-8 h-8 text-text-muted" />}
              />
            ) : showTableAlternative ? (
              /* Accessible Alternative Data Table */
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs border border-border rounded">
                  <caption className="sr-only">Assessment Daily Trend Data Table</caption>
                  <thead className="bg-surface-raised border-b border-border text-text-muted uppercase tracking-wider font-mono">
                    <tr>
                      <th scope="col" className="p-2.5">Date</th>
                      <th scope="col" className="p-2.5">Avg RULA Score</th>
                      <th scope="col" className="p-2.5">Valid Observations</th>
                      <th scope="col" className="p-2.5">Insufficient Observations</th>
                      <th scope="col" className="p-2.5">Invalid Observations</th>
                      <th scope="col" className="p-2.5">Total Samples</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {trendPoints.map((row) => (
                      <tr key={row.date} className="hover:bg-surface-raised/40">
                        <td className="p-2.5 font-mono">{row.date}</td>
                        <td className="p-2.5 font-semibold">
                          {row.average_score !== null && row.average_score !== undefined
                            ? row.average_score.toFixed(1)
                            : "— (No valid data)"}
                        </td>
                        <td className="p-2.5">{row.valid_count}</td>
                        <td className="p-2.5">{row.insufficient_count}</td>
                        <td className="p-2.5">{row.invalid_count}</td>
                        <td className="p-2.5">{row.valid_count + row.insufficient_count + row.invalid_count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              /* Recharts Visual Trend Chart */
              <div
                className="w-full h-64 pt-2"
                tabIndex={0}
                role="region"
                aria-label="Assessment trend line chart showing daily average RULA score"
              >
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={trendPoints} margin={{ top: 10, right: 20, left: -10, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" vertical={false} />
                    <XAxis
                      dataKey="date"
                      stroke="#888888"
                      fontSize={11}
                      tickLine={false}
                      axisLine={{ stroke: "rgba(255,255,255,0.15)" }}
                    />
                    <YAxis
                      domain={[1, 7]}
                      stroke="#888888"
                      fontSize={11}
                      tickLine={false}
                      axisLine={{ stroke: "rgba(255,255,255,0.15)" }}
                      ticks={[1, 2, 3, 4, 5, 6, 7]}
                    />
                    <Tooltip
                      content={({ active, payload }) => {
                        if (!active || !payload || !payload.length) return null;
                        const first = payload[0];
                        if (!first) return null;
                        const pt = first.payload as DashboardTrendPoint;
                        const total = pt.valid_count + pt.insufficient_count + pt.invalid_count;
                        return (
                          <div className="bg-surface-elevated border border-border p-2.5 rounded shadow-lg text-xs space-y-1">
                            <p className="font-mono text-text-muted">{pt.date}</p>
                            <p className="font-semibold text-text-primary">
                              Average RULA: {pt.average_score !== null && pt.average_score !== undefined ? pt.average_score.toFixed(1) : "None (Invalid)"}
                            </p>
                            <p className="text-text-muted text-[11px]">
                              Sample count: {total} ({pt.valid_count} valid, {pt.invalid_count} invalid)
                            </p>
                          </div>
                        );
                      }}
                    />
                    {/* connectNulls={false} enforces NO interpolation across missing/invalid days */}
                    <Line
                      type="monotone"
                      dataKey="average_score"
                      stroke="#0ea5e9"
                      strokeWidth={2.5}
                      dot={{ r: 3, fill: "#0ea5e9" }}
                      activeDot={{ r: 5 }}
                      connectNulls={false}
                      name="Average RULA"
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* Accessible Text Summary */}
            {trendStats && (
              <div className="pt-2 text-xs text-text-muted border-t border-border/40 leading-relaxed">
                <span className="font-semibold text-text-secondary">Trend Summary: </span>
                Across {trendStats.totalDays} calendar days in the window, {trendStats.validDays} days had valid posture telemetry. Daily average scores ranged from a low of {trendStats.minScore} to a high of {trendStats.maxScore} RULA, spanning {trendStats.totalObservations.toLocaleString()} recorded observations.
              </div>
            )}
          </Card>

          {/* Posture Breakdown & Device Status Summary */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Posture Indicator Breakdown */}
            <Card className="lg:col-span-2 space-y-4">
              <div className="border-b border-border/50 pb-2">
                <h3 className="text-sm font-semibold text-text-primary">Posture Indicator Breakdown</h3>
                <p className="text-xs text-text-muted">
                  Anatomical joint angle risk distributions across valid telemetry records.
                </p>
              </div>

              {summary.posture_breakdown &&
              (summary.posture_breakdown.neck_distribution.length > 0 ||
                summary.posture_breakdown.trunk_distribution.length > 0) ? (
                <div className="space-y-4 pt-1">
                  {/* Neck */}
                  <div className="space-y-1.5">
                    <div className="flex justify-between text-xs font-medium">
                      <span>Cervical Spine (Neck Flexion/Extension)</span>
                      <span className="text-text-muted font-mono">
                        {summary.posture_breakdown.neck_distribution.find((d) => d.category === "optimal")?.percentage.toFixed(0) || 0}% Optimal
                      </span>
                    </div>
                    <div className="h-3 w-full bg-surface-muted rounded-full flex overflow-hidden">
                      <div
                        style={{ width: `${summary.posture_breakdown.neck_distribution.find((d) => d.category === "optimal")?.percentage || 0}%` }}
                        className="bg-emerald-500"
                        title={`Optimal: ${summary.posture_breakdown.neck_distribution.find((d) => d.category === "optimal")?.percentage || 0}%`}
                      />
                      <div
                        style={{ width: `${summary.posture_breakdown.neck_distribution.find((d) => d.category === "moderate")?.percentage || 0}%` }}
                        className="bg-amber-500"
                        title={`Moderate: ${summary.posture_breakdown.neck_distribution.find((d) => d.category === "moderate")?.percentage || 0}%`}
                      />
                      <div
                        style={{ width: `${summary.posture_breakdown.neck_distribution.find((d) => d.category === "high")?.percentage || 0}%` }}
                        className="bg-rose-500"
                        title={`High Risk: ${summary.posture_breakdown.neck_distribution.find((d) => d.category === "high")?.percentage || 0}%`}
                      />
                    </div>
                  </div>

                  {/* Trunk */}
                  <div className="space-y-1.5">
                    <div className="flex justify-between text-xs font-medium">
                      <span>Thoracic & Lumbar Trunk (Flexion/Twist)</span>
                      <span className="text-text-muted font-mono">
                        {summary.posture_breakdown.trunk_distribution.find((d) => d.category === "optimal")?.percentage.toFixed(0) || 0}% Optimal
                      </span>
                    </div>
                    <div className="h-3 w-full bg-surface-muted rounded-full flex overflow-hidden">
                      <div
                        style={{ width: `${summary.posture_breakdown.trunk_distribution.find((d) => d.category === "optimal")?.percentage || 0}%` }}
                        className="bg-emerald-500"
                        title={`Optimal: ${summary.posture_breakdown.trunk_distribution.find((d) => d.category === "optimal")?.percentage || 0}%`}
                      />
                      <div
                        style={{ width: `${summary.posture_breakdown.trunk_distribution.find((d) => d.category === "moderate")?.percentage || 0}%` }}
                        className="bg-amber-500"
                        title={`Moderate: ${summary.posture_breakdown.trunk_distribution.find((d) => d.category === "moderate")?.percentage || 0}%`}
                      />
                      <div
                        style={{ width: `${summary.posture_breakdown.trunk_distribution.find((d) => d.category === "high")?.percentage || 0}%` }}
                        className="bg-rose-500"
                        title={`High Risk: ${summary.posture_breakdown.trunk_distribution.find((d) => d.category === "high")?.percentage || 0}%`}
                      />
                    </div>
                  </div>

                  {/* Upper Arms */}
                  <div className="space-y-1.5">
                    <div className="flex justify-between text-xs font-medium">
                      <span>Upper Arm Elevation & Abduction</span>
                      <span className="text-text-muted font-mono">
                        {summary.posture_breakdown.upper_arm_distribution.find((d) => d.category === "optimal")?.percentage.toFixed(0) || 0}% Optimal
                      </span>
                    </div>
                    <div className="h-3 w-full bg-surface-muted rounded-full flex overflow-hidden">
                      <div
                        style={{ width: `${summary.posture_breakdown.upper_arm_distribution.find((d) => d.category === "optimal")?.percentage || 0}%` }}
                        className="bg-emerald-500"
                        title={`Optimal: ${summary.posture_breakdown.upper_arm_distribution.find((d) => d.category === "optimal")?.percentage || 0}%`}
                      />
                      <div
                        style={{ width: `${summary.posture_breakdown.upper_arm_distribution.find((d) => d.category === "moderate")?.percentage || 0}%` }}
                        className="bg-amber-500"
                        title={`Moderate: ${summary.posture_breakdown.upper_arm_distribution.find((d) => d.category === "moderate")?.percentage || 0}%`}
                      />
                      <div
                        style={{ width: `${summary.posture_breakdown.upper_arm_distribution.find((d) => d.category === "high")?.percentage || 0}%` }}
                        className="bg-rose-500"
                        title={`High Risk: ${summary.posture_breakdown.upper_arm_distribution.find((d) => d.category === "high")?.percentage || 0}%`}
                      />
                    </div>
                  </div>

                  {/* Legend */}
                  <div className="flex items-center gap-4 pt-2 text-[11px] text-text-muted">
                    <span className="flex items-center gap-1.5">
                      <span className="w-2.5 h-2.5 rounded-full bg-emerald-500" /> Optimal Angle (Score 1)
                    </span>
                    <span className="flex items-center gap-1.5">
                      <span className="w-2.5 h-2.5 rounded-full bg-amber-500" /> Moderate Deviation (Score 2–3)
                    </span>
                    <span className="flex items-center gap-1.5">
                      <span className="w-2.5 h-2.5 rounded-full bg-rose-500" /> High Deviation (Score 4+)
                    </span>
                  </div>
                </div>
              ) : (
                <div className="py-6 text-center text-xs text-text-muted">
                  Not enough posture breakdown data available for the selected filter window.
                </div>
              )}
            </Card>

            {/* Device Status Summary with Precise Definition */}
            <Card className="space-y-4">
              <div className="border-b border-border/50 pb-2">
                <h3 className="text-sm font-semibold text-text-primary">Workstation Connectivity</h3>
                <p className="text-xs text-text-muted">Active edge agent fleet status</p>
              </div>

              <div className="space-y-3">
                <div className="flex items-baseline justify-between">
                  <span className="text-3xl font-bold tracking-tight text-text-primary">
                    {summary.online_devices_count}
                  </span>
                  <span className="text-xs text-text-muted font-mono">
                    of {summary.active_devices_count} enrolled
                  </span>
                </div>

                <div className="p-3 bg-surface-muted rounded border border-border/60 text-xs space-y-1.5 text-text-secondary leading-relaxed">
                  <div className="flex items-center gap-1.5 font-medium text-text-primary">
                    <Info className="w-3.5 h-3.5 text-accent" />
                    <span>Precise Online Definition</span>
                  </div>
                  <p className="text-[11px] text-text-muted">
                    A workstation is marked <strong>Online</strong> if a cryptographically authenticated heartbeat or assessment event was received within the last 450 seconds (7.5 minutes).
                  </p>
                  <p className="text-[11px] text-text-muted border-t border-border/40 pt-1">
                    Workstation status strictly reflects telemetry transport state and <strong>never implies live camera access or audio feed</strong>.
                  </p>
                </div>

                {profile?.role === "admin" && (
                  <Link
                    to="/devices"
                    className="inline-flex items-center gap-1 text-xs text-accent hover:underline font-medium pt-1"
                  >
                    <span>Manage fleet devices</span>
                    <ArrowRight className="w-3 h-3" />
                  </Link>
                )}
              </div>
            </Card>
          </div>

          {/* Recent Assessments & Practical Guidance Panel */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Recent Assessments List */}
            <Card className="space-y-3">
              <div className="flex items-center justify-between pb-2 border-b border-border/50">
                <div>
                  <h3 className="text-sm font-semibold text-text-primary">Recent Assessments</h3>
                  <p className="text-xs text-text-muted">Latest edge telemetry events</p>
                </div>
                <Link
                  to="/assessments"
                  className="text-xs text-accent hover:underline inline-flex items-center gap-1 font-medium"
                >
                  View All
                  <ArrowRight className="w-3 h-3" />
                </Link>
              </div>

              {recentAssessments && recentAssessments.length > 0 ? (
                <div className="divide-y divide-border/40">
                  {recentAssessments.map((item) => (
                    <div key={item.event_id} className="py-2.5 flex items-center justify-between gap-3 text-xs">
                      <div>
                        <p className="font-mono text-text-secondary">
                          {new Date(item.captured_at).toLocaleString()}
                        </p>
                        <p className="text-text-muted text-[11px]">
                          Device: {item.device_id.slice(0, 8)}... &bull; Method: {item.scoring_method} v{item.scoring_version}
                        </p>
                      </div>

                      <div className="flex items-center gap-2">
                        {item.validity === "valid" ? (
                          <Badge variant="success" label="Valid" />
                        ) : item.validity === "insufficient" ? (
                          <Badge variant="warning" label="Insufficient" />
                        ) : (
                          <Badge variant="danger" label="Invalid" />
                        )}

                        <span className="font-semibold text-text-primary font-mono w-14 text-right">
                          {item.score !== null ? `RULA ${item.score}` : "—"}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="py-8 text-center text-xs text-text-muted">
                  No recent assessments recorded.
                </div>
              )}
            </Card>

            {/* Practical Guidance Panel */}
            <Card className="space-y-3">
              <div className="pb-2 border-b border-border/50">
                <h3 className="text-sm font-semibold text-text-primary">Practical Guidance</h3>
                <p className="text-xs text-text-muted">
                  Evidence-linked ergonomic setup guidelines
                </p>
              </div>

              <div className="p-3 bg-surface-muted rounded border border-border/60 text-xs space-y-2">
                <div className="flex items-center gap-1.5 font-medium text-emerald-400">
                  <CheckCircle2 className="w-4 h-4" />
                  <span>General Ergonomic Baseline</span>
                </div>
                <ul className="list-disc pl-4 space-y-1 text-text-muted text-[11px] leading-relaxed">
                  <li>
                    <strong>Display Alignment:</strong> Position primary monitor directly in front with upper third at eye height.
                  </li>
                  <li>
                    <strong>Forearm Support:</strong> Keep keyboard and mouse close to table edge so elbows remain at approximately 90–100°.
                  </li>
                  <li>
                    <strong>Lumbar Contact:</strong> Adjust chair backrest angle to maintain firm lumbar contact.
                  </li>
                  <li>
                    <strong>Movement Interval:</strong> Stand or change posture every 45–60 minutes to reduce static muscular load.
                  </li>
                </ul>
              </div>
            </Card>
          </div>
        </>
      )}
    </div>
  );
};
