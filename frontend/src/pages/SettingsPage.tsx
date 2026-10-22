import React from "react";
import {
  User,
  Shield,
  Lock,
  Database,
  Clock,
  Info,
  CheckCircle2,
  Building,
} from "lucide-react";
import { useAuth } from "../features/auth/AuthContext";
import { useUserProfile } from "../features/auth/UserProfileContext";
import { PageHeader } from "../components/ui/PageHeader";
import { Card } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";

export const SettingsPage: React.FC = () => {
  const { user, signOut } = useAuth();
  const { profile } = useUserProfile();

  const userEmail = profile?.email || user?.email || "Unknown";
  const userRole = profile?.role || "reviewer";
  const orgSlug = profile?.organization_slug || "default-org";
  const orgId = profile?.organization_id || "N/A";
  const userId = profile?.user_id || user?.id || "N/A";

  return (
    <div className="space-y-8 max-w-4xl">
      <PageHeader
        title="Settings & Privacy"
        subtitle="Manage your account profile, review tenant configurations, and inspect data privacy transparency controls."
      />

      {/* Account Section */}
      <section aria-labelledby="section-account">
        <h2 id="section-account" className="text-base font-semibold text-text-primary mb-3 flex items-center gap-2">
          <User className="w-5 h-5 text-accent" />
          <span>Account & Organization</span>
        </h2>
        <Card className="divide-y divide-border/60 p-0 overflow-hidden">
          <div className="p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <div>
              <span className="text-xs text-text-muted">Email address</span>
              <p className="text-sm font-medium text-text-primary mt-0.5">{userEmail}</p>
            </div>
            <Badge
              variant={userRole === "admin" ? "accent" : "neutral"}
              label={userRole === "admin" ? "Organization Admin" : "Reviewer"}
            />
          </div>

          <div className="p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <div>
              <span className="text-xs text-text-muted">Organization</span>
              <p className="text-sm font-medium text-text-primary mt-0.5 flex items-center gap-2">
                <Building className="w-4 h-4 text-text-muted" />
                <span>{orgSlug}</span>
              </p>
            </div>
            <div className="text-xs text-text-muted font-mono">Org ID: {orgId}</div>
          </div>

          <div className="p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <div>
              <span className="text-xs text-text-muted">User ID</span>
              <p className="text-xs font-mono text-text-secondary mt-0.5">{userId}</p>
            </div>
            <Button variant="outline" size="sm" onClick={() => signOut()}>
              Sign out
            </Button>
          </div>
        </Card>
      </section>

      {/* Privacy & Transparency Section (Mandatory PRD/DESIGN.md Content) */}
      <section id="privacy" aria-labelledby="section-privacy">
        <h2 id="section-privacy" className="text-base font-semibold text-text-primary mb-3 flex items-center gap-2">
          <Lock className="w-5 h-5 text-accent" />
          <span>Privacy & Data Transparency</span>
        </h2>

        <div className="space-y-4">
          {/* Exact statement from DESIGN.md §9 */}
          <div className="rounded-card border border-accent/40 bg-[#161224] p-5 sm:p-6 shadow-sm">
            <div className="flex items-start gap-3">
              <Shield className="w-6 h-6 text-accent shrink-0 mt-0.5" aria-hidden="true" />
              <div>
                <h3 className="text-sm font-semibold text-white mb-2">
                  Workstation-Local Processing Guarantee
                </h3>
                <blockquote className="text-sm text-text-primary/95 italic leading-relaxed border-l-2 border-accent pl-3.5 my-2">
                  “Camera frames are processed on this workstation. EdgeErgo does not upload raw video, face crops, or raw pose landmarks. Only the configured assessment summaries and necessary operational metadata are synchronized.”
                </blockquote>
                <p className="text-xs text-text-secondary mt-3">
                  This architecture is mathematically enforced by client-side inference pipelines and zero-trust ingestion schemas (<code className="text-accent">extra="forbid"</code>).
                </p>
              </div>
            </div>
          </div>

          {/* Telemetry Allowlist */}
          <Card>
            <h3 className="text-sm font-semibold text-text-primary mb-2 flex items-center gap-2">
              <Database className="w-4 h-4 text-accent" />
              <span>What Synchronizes to Central Services</span>
            </h3>
            <p className="text-xs text-text-secondary mb-4">
              Only allowlisted posture screening summaries are sent over TLS 1.3 to the hosted API:
            </p>
            <ul className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs text-text-secondary">
              <li className="flex items-center gap-2 p-2 rounded-control bg-surface-raised border border-border">
                <CheckCircle2 className="w-4 h-4 text-success shrink-0" />
                <span>Synthetic Event UUID & UTC Timestamp</span>
              </li>
              <li className="flex items-center gap-2 p-2 rounded-control bg-surface-raised border border-border">
                <CheckCircle2 className="w-4 h-4 text-success shrink-0" />
                <span>Validity state (valid, insufficient, invalid)</span>
              </li>
              <li className="flex items-center gap-2 p-2 rounded-control bg-surface-raised border border-border">
                <CheckCircle2 className="w-4 h-4 text-success shrink-0" />
                <span>Computed partial RULA screening risk score (1–7)</span>
              </li>
              <li className="flex items-center gap-2 p-2 rounded-control bg-surface-raised border border-border">
                <CheckCircle2 className="w-4 h-4 text-success shrink-0" />
                <span>Segment subscores (Neck, Trunk, Upper Arm)</span>
              </li>
              <li className="flex items-center gap-2 p-2 rounded-control bg-surface-raised border border-border">
                <CheckCircle2 className="w-4 h-4 text-success shrink-0" />
                <span>Standard ergonomic guidance codes (e.g. NECK_FLEXION)</span>
              </li>
              <li className="flex items-center gap-2 p-2 rounded-control bg-surface-raised border border-border">
                <CheckCircle2 className="w-4 h-4 text-success shrink-0" />
                <span>Agent software version & device heartbeat</span>
              </li>
            </ul>
          </Card>

          {/* Data Retention Policies (from docs/DECISIONS.md) */}
          <Card>
            <h3 className="text-sm font-semibold text-text-primary mb-2 flex items-center gap-2">
              <Clock className="w-4 h-4 text-accent" />
              <span>Data Retention & Automatic Purge Schedule</span>
            </h3>
            <p className="text-xs text-text-secondary mb-4 leading-relaxed">
              In accordance with enterprise data minimization guidelines recorded in <code className="text-text-muted">docs/DECISIONS.md</code>, historical records are automatically purged via nightly scheduled database maintenance:
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
              <div className="p-3.5 rounded-control bg-surface-raised border border-border">
                <span className="text-text-muted block font-medium">Assessment Events</span>
                <span className="text-lg font-semibold text-text-primary mt-1 block">365 Days</span>
                <span className="text-[11px] text-text-muted mt-1 block">Retained for annual trends</span>
              </div>
              <div className="p-3.5 rounded-control bg-surface-raised border border-border">
                <span className="text-text-muted block font-medium">Device Heartbeats</span>
                <span className="text-lg font-semibold text-text-primary mt-1 block">30 Days</span>
                <span className="text-[11px] text-text-muted mt-1 block">Rolling connectivity window</span>
              </div>
              <div className="p-3.5 rounded-control bg-surface-raised border border-border">
                <span className="text-text-muted block font-medium">Security Audit Logs</span>
                <span className="text-lg font-semibold text-text-primary mt-1 block">365 Days</span>
                <span className="text-[11px] text-text-muted mt-1 block">Compliance & accountability</span>
              </div>
            </div>
          </Card>

          {/* Non-Diagnostic Disclaimer Notice */}
          <div className="p-4 rounded-control bg-surface-raised border border-border/80 flex items-start gap-3 text-xs text-text-secondary leading-relaxed">
            <Info className="w-4 h-4 text-accent shrink-0 mt-0.5" aria-hidden="true" />
            <div>
              <strong className="text-text-primary block mb-0.5">Scientific & Diagnostic Disclaimer</strong>
              EdgeErgo is a workplace ergonomic screening indicator and posture adjustment prompt. It is not a medical device, cannot diagnose musculoskeletal disorders, and must never be used for employee disciplinary action or productivity evaluations.
            </div>
          </div>
        </div>
      </section>
    </div>
  );
};
