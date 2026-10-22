import React, { useState, useCallback, useEffect } from "react";
import {
  Laptop,
  Plus,
  ShieldCheck,
  Clock,
  RefreshCw,
  Copy,
  Check,
  AlertTriangle,
  History,
  X,
  Lock,
} from "lucide-react";
import { PageHeader } from "../components/ui/PageHeader";
import { Card } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { Table, Column } from "../components/ui/Table";
import { ConfirmDialog } from "../components/ui/ConfirmDialog";
import { EmptyState } from "../components/ui/EmptyState";
import { ErrorState } from "../components/ui/ErrorState";
import { StaleDataBanner } from "../components/ui/StaleDataBanner";
import { useToast } from "../components/ui/Toast";
import { useAuth } from "../features/auth/AuthContext";
import { useUserProfile } from "../features/auth/UserProfileContext";
import {
  useDevFixture,
  MOCK_DEVICES,
  MOCK_AUDIT_LOG,
} from "../lib/devFixtures";
import {
  fetchDevices,
  createEnrollmentToken,
  revokeDevice,
  fetchAuditEvents,
  DeviceListItem,
  TokenCreateResponse,
  AuditEventItem,
} from "../lib/api";
import { useApiData } from "../lib/useApiData";

function getSafeStatusBadge(status: string) {
  switch (status.toLowerCase()) {
    case "online":
      return <Badge variant="success" label="● Online" />;
    case "offline":
      return <Badge variant="neutral" label="○ Offline" />;
    case "pending":
      return <Badge variant="warning" label="⏳ Sync Pending" />;
    case "attention_needed":
      return <Badge variant="warning" label="⚠️ Attention Needed" />;
    case "revoked":
      return <Badge variant="danger" label="✕ Revoked" />;
    default:
      return <Badge variant="neutral" label="? Unknown" />;
  }
}

function formatRelativeTime(dateStr: string | null | undefined): string {
  if (!dateStr) return "Never";
  const diffSec = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000);
  if (diffSec < 60) return `${diffSec}s ago`;
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
  return `${Math.floor(diffSec / 86400)}d ago`;
}

export const DevicesPage: React.FC = () => {
  const { accessToken } = useAuth();
  const { profile } = useUserProfile();
  const { isDevFixtureActive } = useDevFixture();
  const { showToast } = useToast();

  const isAdmin = profile?.role === "admin";

  // Modal / Drawer states
  const [isEnrollModalOpen, setIsEnrollModalOpen] = useState(false);
  const [deviceToRevoke, setDeviceToRevoke] = useState<DeviceListItem | null>(null);
  const [isRevoking, setIsRevoking] = useState(false);
  const [auditDevice, setAuditDevice] = useState<DeviceListItem | null>(null);

  // Single-use token issuance state (cleared immediately upon dismissal)
  const [tokenLabel, setTokenLabel] = useState("");
  const [tokenExpiresMinutes, setTokenExpiresMinutes] = useState(60);
  const [isCreatingToken, setIsCreatingToken] = useState(false);
  const [issuedToken, setIssuedToken] = useState<TokenCreateResponse | null>(null);
  const [tokenCopied, setTokenCopied] = useState(false);
  const [remainingSeconds, setRemainingSeconds] = useState<number | null>(null);

  // Devices Query
  const devicesFetcher = useCallback(
    async (signal: AbortSignal): Promise<DeviceListItem[]> => {
      if (import.meta.env.DEV && isDevFixtureActive) return MOCK_DEVICES;
      if (!accessToken) throw new Error("Missing access token");
      return fetchDevices(accessToken, signal);
    },
    [accessToken, isDevFixtureActive]
  );

  const {
    data: devices,
    loading,
    error,
    isStale,
    lastUpdated,
    refetch,
  } = useApiData<DeviceListItem[]>({
    fetcher: devicesFetcher,
    enabled: Boolean(accessToken || isDevFixtureActive),
    deps: [devicesFetcher],
  });

  // Countdown timer for issued token
  useEffect(() => {
    if (!issuedToken) {
      setRemainingSeconds(null);
      return;
    }
    const updateCountdown = () => {
      const remaining = Math.max(
        0,
        Math.floor((new Date(issuedToken.expires_at).getTime() - Date.now()) / 1000)
      );
      setRemainingSeconds(remaining);
    };
    updateCountdown();
    const interval = setInterval(updateCountdown, 1000);
    return () => clearInterval(interval);
  }, [issuedToken]);

  // Handle Token Creation
  const handleCreateToken = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isAdmin) return;
    if (!tokenLabel.trim()) {
      showToast("Device label is required.", "error");
      return;
    }

    setIsCreatingToken(true);
    try {
      if (import.meta.env.DEV && isDevFixtureActive) {
        setIssuedToken({
          token: `eet_dev_fixture_${Math.random().toString(36).substring(2, 15)}`,
          expires_at: new Date(Date.now() + tokenExpiresMinutes * 60000).toISOString(),
          label: tokenLabel.trim(),
        });
      } else {
        const res = await createEnrollmentToken(accessToken!, {
          label: tokenLabel.trim(),
          expires_in_minutes: tokenExpiresMinutes,
        });
        setIssuedToken(res);
      }
      showToast("Enrollment token generated. Copy it now; it will not be shown again.", "success");
    } catch (err: unknown) {
      showToast((err as Error).message || "An error occurred generating the enrollment token.", "error");
    } finally {
      setIsCreatingToken(false);
    }
  };

  const handleDismissTokenModal = () => {
    // Purge plaintext token immediately from state
    setIssuedToken(null);
    setTokenLabel("");
    setTokenExpiresMinutes(60);
    setTokenCopied(false);
    setIsEnrollModalOpen(false);
    refetch();
  };

  const handleCopyToken = () => {
    if (!issuedToken) return;
    navigator.clipboard.writeText(issuedToken.token);
    setTokenCopied(true);
    showToast("Plaintext token copied to clipboard.", "info");
    setTimeout(() => setTokenCopied(false), 2000);
  };

  // Handle Device Revocation
  const handleConfirmRevoke = async () => {
    if (!deviceToRevoke || !isAdmin) return;
    setIsRevoking(true);
    try {
      if (import.meta.env.DEV && isDevFixtureActive) {
        showToast(`Workstation ${deviceToRevoke.label} marked as revoked in dev mode.`, "success");
      } else {
        await revokeDevice(accessToken!, deviceToRevoke.id);
        showToast(`Workstation ${deviceToRevoke.label} credential was permanently invalidated.`, "success");
      }
      setDeviceToRevoke(null);
      refetch();
    } catch (err: unknown) {
      showToast((err as Error).message || "Unable to revoke workstation credential.", "error");
    } finally {
      setIsRevoking(false);
    }
  };

  // Audit Events Fetcher for selected device
  const auditFetcher = useCallback(
    async (signal: AbortSignal): Promise<AuditEventItem[]> => {
      if (!auditDevice) return [];
      if (import.meta.env.DEV && isDevFixtureActive) return MOCK_AUDIT_LOG.items;
      if (!accessToken) return [];
      const res = await fetchAuditEvents(
        accessToken,
        {
          target_id: auditDevice.id,
        },
        signal
      );
      return res.items;
    },
    [auditDevice, accessToken, isDevFixtureActive]
  );

  const { data: auditEvents, loading: auditLoading } = useApiData<AuditEventItem[]>({
    fetcher: auditFetcher,
    enabled: Boolean(auditDevice),
    deps: [auditDevice],
  });

  // Table Columns
  const columns: Column<DeviceListItem>[] = [
    {
      key: "label",
      header: "Workstation Label",
      render: (d) => (
        <div>
          <span className="font-semibold text-text-primary text-sm block">{d.label}</span>
          <span className="font-mono text-xs text-text-muted">{d.public_id}</span>
        </div>
      ),
    },
    {
      key: "status",
      header: "Status",
      render: (d) => getSafeStatusBadge(d.computed_status || d.status),
    },
    {
      key: "agent_version",
      header: "Agent Version",
      className: "font-mono text-xs",
      render: (d) => `v${d.agent_version || "1.0.0"}`,
    },
    {
      key: "last_seen_at",
      header: "Last Heartbeat",
      className: "text-xs text-text-muted",
      render: (d) => formatRelativeTime(d.last_seen_at),
    },
    {
      key: "last_sync_at",
      header: "Last Sync",
      className: "text-xs text-text-muted",
      render: (d) => formatRelativeTime(d.last_sync_at),
    },
    {
      key: "pending_queue",
      header: "Pending Sync Queue",
      className: "text-xs font-mono",
      render: (d) => `${d.pending_queue_count || 0} batches`,
    },
    {
      key: "actions",
      header: "Actions",
      className: "text-right",
      render: (d) => (
        <div className="flex items-center justify-end gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setAuditDevice(d)}
            aria-label={`View audit logs for ${d.label}`}
            icon={<History className="w-3.5 h-3.5" />}
          >
            Audit
          </Button>

          {isAdmin ? (
            d.status !== "revoked" && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setDeviceToRevoke(d)}
                aria-label={`Revoke credentials for ${d.label}`}
                className="text-danger hover:bg-danger/10 border-danger/30"
              >
                Revoke
              </Button>
            )
          ) : (
            <span className="text-[11px] text-text-muted italic">Read-only</span>
          )}
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-2 border-b border-border/50">
        <div>
          <PageHeader
            title="Enrolled Workstations"
            subtitle="Manage edge agent enrollment, credentials, and synchronization health across enterprise workstations."
          />
          {!isAdmin && (
            <div className="mt-2 inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-surface-muted text-text-muted text-xs border border-border">
              <Lock className="w-3 h-3 text-amber-400" />
              <span>Reviewer Mode: Device controls are read-only. Administrator role required for enrollment and revocation.</span>
            </div>
          )}
        </div>

        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            size="sm"
            onClick={() => refetch()}
            disabled={loading}
            icon={<RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />}
            aria-label="Refresh workstation fleet"
          >
            Refresh
          </Button>

          {isAdmin ? (
            <Button
              variant="primary"
              size="sm"
              onClick={() => setIsEnrollModalOpen(true)}
              icon={<Plus className="w-4 h-4" />}
            >
              Enroll Workstation
            </Button>
          ) : (
            <Button
              variant="outline"
              size="sm"
              disabled
              title="Admin privileges required to enroll devices"
              icon={<Lock className="w-3.5 h-3.5" />}
            >
              Enroll Workstation
            </Button>
          )}
        </div>
      </div>

      {/* Privacy Notice Card */}
      <Card className="bg-surface-raised/40 border-border/80 p-4">
        <div className="flex items-start gap-3">
          <ShieldCheck className="w-5 h-5 text-accent shrink-0 mt-0.5" />
          <div className="space-y-1 text-xs text-text-secondary leading-relaxed">
            <p className="font-semibold text-text-primary">
              Edge Transport & Privacy Architecture
            </p>
            <p>
              Workstation status labels (Online, Offline, Sync Pending) strictly indicate telemetry HTTP/TLS transport availability between the local EdgeErgo agent and the hosted platform.
              <strong> Device status NEVER implies live camera access, video streaming, or background microphone recording.</strong> All posture assessment models execute strictly within local machine memory.
            </p>
          </div>
        </div>
      </Card>

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
          title="Failed to Load Workstations"
          message={error.message || "An error occurred fetching workstation devices."}
          onRetry={refetch}
        />
      )}

      {/* Main Table */}
      <Table<DeviceListItem>
        columns={columns}
        data={devices || []}
        keyExtractor={(d) => d.id}
        loading={loading && (!devices || devices.length === 0)}
        emptyState={
          <EmptyState
            title="No Workstations Enrolled"
            description="No workstation agents are currently registered for this organization. Generate an enrollment token to connect your first edge agent."
            icon={<Laptop className="w-8 h-8 text-text-muted" />}
          />
        }
      />

      {/* Create Enrollment Token Modal (Admin Only) */}
      {isEnrollModalOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-xs"
          role="dialog"
          aria-modal="true"
          aria-labelledby="enroll-modal-title"
        >
          <div className="w-full max-w-lg bg-surface border border-border rounded-card p-6 shadow-2xl relative space-y-4">
            <button
              onClick={handleDismissTokenModal}
              className="absolute top-4 right-4 text-text-muted hover:text-text-primary p-2 focus:outline-none focus:ring-2 focus:ring-accent rounded"
              aria-label="Close enrollment modal"
            >
              <X className="w-5 h-5" />
            </button>

            {!issuedToken ? (
              <form onSubmit={handleCreateToken} className="space-y-4">
                <div>
                  <h2 id="enroll-modal-title" className="text-base font-semibold text-text-primary">
                    Generate Workstation Enrollment Token
                  </h2>
                  <p className="text-xs text-text-muted mt-1">
                    Issues a short-lived single-use token to enroll a new workstation desktop agent into this organization.
                  </p>
                </div>

                <div className="space-y-3">
                  <div>
                    <label htmlFor="token-label-input" className="block text-xs font-medium text-text-secondary mb-1">
                      Workstation Label / Identifier *
                    </label>
                    <Input
                      id="token-label-input"
                      type="text"
                      placeholder="e.g. Workstation #14 — Engineering"
                      value={tokenLabel}
                      onChange={(e) => setTokenLabel(e.target.value)}
                      required
                    />
                  </div>

                  <div>
                    <label htmlFor="token-expiry-input" className="block text-xs font-medium text-text-secondary mb-1">
                      Token Validity Window (Minutes)
                    </label>
                    <Input
                      id="token-expiry-input"
                      type="number"
                      min={5}
                      max={1440}
                      value={tokenExpiresMinutes}
                      onChange={(e) => setTokenExpiresMinutes(parseInt(e.target.value, 10) || 60)}
                    />
                    <p className="text-[11px] text-text-muted mt-1">
                      Recommended: 60 minutes. The token expires automatically if not consumed.
                    </p>
                  </div>
                </div>

                <div className="flex justify-end gap-3 pt-3 border-t border-border">
                  <Button variant="outline" type="button" onClick={handleDismissTokenModal}>
                    Cancel
                  </Button>
                  <Button variant="primary" type="submit" loading={isCreatingToken}>
                    Generate Token
                  </Button>
                </div>
              </form>
            ) : (
              <div className="space-y-4">
                <div>
                  <h2 id="enroll-modal-title" className="text-base font-semibold text-text-primary">
                    Single-Use Enrollment Token
                  </h2>
                  <p className="text-xs text-text-muted mt-1">
                    Workstation: <strong className="text-text-primary">{issuedToken.label}</strong>
                  </p>
                </div>

                <div className="p-3 bg-amber-500/10 border border-amber-500/30 rounded text-xs text-amber-200 flex items-start gap-2">
                  <AlertTriangle className="w-4 h-4 shrink-0 text-amber-400 mt-0.5" />
                  <div>
                    <strong className="block">Show Once Guarantee:</strong>
                    This plaintext token will <strong>never</strong> be displayed again or stored in localStorage once dismissed. Copy it now.
                  </div>
                </div>

                <div className="space-y-2">
                  <div className="p-3 bg-surface-muted rounded border border-border flex items-center justify-between gap-3">
                    <span className="font-mono text-sm break-all text-text-primary select-all">
                      {issuedToken.token}
                    </span>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handleCopyToken}
                      icon={tokenCopied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                    >
                      {tokenCopied ? "Copied" : "Copy"}
                    </Button>
                  </div>

                  {remainingSeconds !== null && (
                    <div className="flex items-center gap-1.5 text-xs text-text-muted font-mono">
                      <Clock className="w-3.5 h-3.5" />
                      <span>
                        Expires in: {Math.floor(remainingSeconds / 60)}m {remainingSeconds % 60}s
                      </span>
                    </div>
                  )}
                </div>

                <div className="p-3 rounded bg-surface-raised/40 border border-border text-xs text-text-secondary space-y-1">
                  <p className="font-medium text-text-primary">Next Steps for Setup:</p>
                  <ol className="list-decimal pl-4 space-y-1 text-text-muted text-[11px]">
                    <li>Open terminal on the target workstation.</li>
                    <li>Run: <code className="bg-surface px-1.5 py-0.5 rounded font-mono text-accent">edge-ergo enroll --token {issuedToken.token.slice(0, 12)}...</code></li>
                    <li>The agent will exchange this token for permanent hardware-bound credentials.</li>
                  </ol>
                </div>

                <div className="flex justify-end pt-3 border-t border-border">
                  <Button variant="primary" onClick={handleDismissTokenModal}>
                    I Have Saved the Token
                  </Button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Revocation Confirmation Dialog */}
      <ConfirmDialog
        isOpen={Boolean(deviceToRevoke)}
        title="Revoke Workstation Credential?"
        description={
          deviceToRevoke
            ? `Are you sure you want to permanently revoke credentials for "${deviceToRevoke.label}" (${deviceToRevoke.public_id})? Once revoked, the edge agent will be permanently barred from submitting telemetry. Existing historical assessments remain safely stored in audit logs.`
            : ""
        }
        confirmLabel="Revoke Workstation"
        cancelLabel="Cancel"
        variant="danger"
        loading={isRevoking}
        onConfirm={handleConfirmRevoke}
        onCancel={() => setDeviceToRevoke(null)}
      />

      {/* Audit History Drawer */}
      {auditDevice && (
        <div
          className="fixed inset-0 z-50 overflow-hidden bg-black/60 backdrop-blur-xs flex justify-end"
          role="dialog"
          aria-modal="true"
          aria-labelledby="audit-drawer-title"
        >
          <div className="w-full max-w-lg bg-surface border-l border-border h-full overflow-y-auto p-6 flex flex-col justify-between shadow-2xl">
            <div className="space-y-6">
              <div className="flex items-start justify-between gap-4 pb-4 border-b border-border">
                <div>
                  <h2 id="audit-drawer-title" className="text-base font-semibold text-text-primary">
                    Workstation Audit Trail
                  </h2>
                  <p className="text-xs font-mono text-text-muted mt-0.5">
                    Target: {auditDevice.label} ({auditDevice.public_id})
                  </p>
                </div>
                <button
                  onClick={() => setAuditDevice(null)}
                  className="p-1 rounded hover:bg-surface-raised text-text-muted hover:text-text-primary"
                  aria-label="Close audit drawer"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {auditLoading ? (
                <div className="space-y-3">
                  <div className="h-16 bg-surface-muted rounded animate-pulse" />
                  <div className="h-16 bg-surface-muted rounded animate-pulse" />
                </div>
              ) : auditEvents && auditEvents.length > 0 ? (
                <div className="space-y-3">
                  {auditEvents.map((evt) => (
                    <div
                      key={evt.id}
                      className="p-3 rounded bg-surface-muted border border-border text-xs space-y-1"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-mono font-semibold text-accent">{evt.action}</span>
                        <span className="text-[11px] text-text-muted font-mono">
                          {new Date(evt.created_at).toLocaleString()}
                        </span>
                      </div>
                      <p className="text-text-muted text-[11px]">
                        Actor ID: {(evt.metadata?.actor_id as string) || "System Agent (Self-Enrolled)"}
                      </p>
                      {evt.metadata && (
                        <pre className="mt-1 p-2 bg-surface rounded text-[10px] text-text-secondary overflow-x-auto font-mono">
                          {JSON.stringify(evt.metadata, null, 2)}
                        </pre>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="py-12 text-center text-xs text-text-muted">
                  No audit log events recorded for this workstation.
                </div>
              )}
            </div>

            <div className="pt-4 border-t border-border">
              <Button variant="outline" className="w-full" onClick={() => setAuditDevice(null)}>
                Close Audit History
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
