-- EdgeErgo V3 — Migration 1: Core Schema & Constraints
-- Version: 20261020120000
-- Source of Truth: PRD.md §8, TECH_STACK.md §4, docs/DECISIONS.md

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 1. Create dedicated least-privilege backend application role
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'edgeergo_api') THEN
    CREATE ROLE edgeergo_api NOLOGIN;
  END IF;
END
$$;

-- 2. Organizations (Tenant boundary)
CREATE TABLE IF NOT EXISTS public.organizations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL CHECK (length(trim(name)) >= 2),
  slug text UNIQUE NOT NULL CHECK (slug ~ '^[a-z0-9-]+$'),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- 3. User Profiles (Mirrors Supabase auth.users)
CREATE TABLE IF NOT EXISTS public.profiles (
  id uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  display_name text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- 4. Organization Memberships & Roles (Strictly 'admin' or 'reviewer')
CREATE TABLE IF NOT EXISTS public.organization_members (
  organization_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  user_id uuid NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  role text NOT NULL CHECK (role IN ('admin', 'reviewer')),
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (organization_id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_org_members_user ON public.organization_members(user_id, organization_id);

-- 5. Devices (Workstation endpoints; stores only SHA-256 hash of secret)
CREATE TABLE IF NOT EXISTS public.devices (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  label text NOT NULL CHECK (length(trim(label)) >= 1),
  status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'active', 'revoked')),
  public_id text UNIQUE NOT NULL CHECK (public_id ~ '^[a-zA-Z0-9_-]+$'),
  credential_hash text NOT NULL,
  enrolled_at timestamptz,
  revoked_at timestamptz,
  last_seen_at timestamptz,
  last_sync_at timestamptz,
  agent_version text,
  credential_version integer NOT NULL DEFAULT 1,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_devices_org_status ON public.devices(organization_id, status);
CREATE INDEX IF NOT EXISTS idx_devices_public_id ON public.devices(public_id);

-- 6. Device Enrollment Tokens (Short-lived, single-use, hashed)
CREATE TABLE IF NOT EXISTS public.device_enrollment_tokens (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  token_hash text UNIQUE NOT NULL,
  organization_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  created_by uuid REFERENCES public.profiles(id) ON DELETE SET NULL,
  label text NOT NULL,
  expires_at timestamptz NOT NULL,
  consumed_at timestamptz,
  consumed_by_device_id uuid REFERENCES public.devices(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_enrollment_tokens_org ON public.device_enrollment_tokens(organization_id, expires_at);

-- 7. Assessment Events (Minimized ergonomic observations; typed numeric columns; no raw landmarks)
CREATE TABLE IF NOT EXISTS public.assessment_events (
  event_id uuid NOT NULL,
  device_id uuid NOT NULL REFERENCES public.devices(id) ON DELETE CASCADE,
  organization_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  captured_at timestamptz NOT NULL,
  received_at timestamptz NOT NULL DEFAULT now(),
  scoring_method text NOT NULL,
  scoring_version text NOT NULL,
  validity text NOT NULL CHECK (validity IN ('valid', 'insufficient', 'invalid')),
  score numeric(4,2) CHECK (score IS NULL OR (score >= 1.0 AND score <= 7.0)),
  neck_score integer CHECK (neck_score IS NULL OR (neck_score >= 1 AND neck_score <= 6)),
  trunk_score integer CHECK (trunk_score IS NULL OR (trunk_score >= 1 AND trunk_score <= 6)),
  upper_arm_score integer CHECK (upper_arm_score IS NULL OR (upper_arm_score >= 1 AND upper_arm_score <= 6)),
  neck_angle_deg numeric(5,2) CHECK (neck_angle_deg IS NULL OR (neck_angle_deg >= -90.0 AND neck_angle_deg <= 90.0)),
  trunk_angle_deg numeric(5,2) CHECK (trunk_angle_deg IS NULL OR (trunk_angle_deg >= -90.0 AND trunk_angle_deg <= 90.0)),
  shoulder_elevation_deg numeric(5,2) CHECK (shoulder_elevation_deg IS NULL OR (shoulder_elevation_deg >= 0.0 AND shoulder_elevation_deg <= 180.0)),
  upper_arm_angle_deg numeric(5,2) CHECK (upper_arm_angle_deg IS NULL OR (upper_arm_angle_deg >= 0.0 AND upper_arm_angle_deg <= 180.0)),
  guidance_codes text[] NOT NULL DEFAULT '{}',
  software_version text NOT NULL,
  CONSTRAINT pk_assessment_events PRIMARY KEY (device_id, event_id),
  CONSTRAINT uq_assessment_events_idempotent UNIQUE (device_id, event_id),
  -- Score must be present if and only if observation is valid (FR-014)
  CONSTRAINT chk_assessment_score_validity CHECK (
    (validity = 'valid' AND score IS NOT NULL) OR
    (validity != 'valid' AND score IS NULL)
  )
);
CREATE INDEX IF NOT EXISTS idx_assessment_events_org_captured ON public.assessment_events(organization_id, captured_at DESC);
CREATE INDEX IF NOT EXISTS idx_assessment_events_device_captured ON public.assessment_events(device_id, captured_at DESC);
CREATE INDEX IF NOT EXISTS idx_assessment_events_org_validity ON public.assessment_events(organization_id, validity);

-- 8. Device Heartbeats (Status & queue monitoring without raw video/frames)
CREATE TABLE IF NOT EXISTS public.device_heartbeats (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  device_id uuid NOT NULL REFERENCES public.devices(id) ON DELETE CASCADE,
  organization_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  received_at timestamptz NOT NULL DEFAULT now(),
  agent_version text NOT NULL,
  queue_depth integer NOT NULL DEFAULT 0 CHECK (queue_depth >= 0),
  state text NOT NULL CHECK (state IN ('ready', 'active', 'paused', 'low_confidence', 'unavailable', 'offline', 'syncing', 'error'))
);
CREATE INDEX IF NOT EXISTS idx_heartbeats_device ON public.device_heartbeats(device_id, received_at DESC);
CREATE INDEX IF NOT EXISTS idx_heartbeats_org ON public.device_heartbeats(organization_id, received_at DESC);

-- 9. Audit Events (Security & compliance trail; rejects secret-like keys in metadata)
CREATE TABLE IF NOT EXISTS public.audit_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  actor_user_id uuid REFERENCES public.profiles(id) ON DELETE SET NULL,
  actor_device_id uuid REFERENCES public.devices(id) ON DELETE SET NULL,
  action text NOT NULL,
  target_type text NOT NULL,
  target_id text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  CONSTRAINT chk_audit_no_secrets CHECK (
    NOT (metadata ?| ARRAY['secret', 'password', 'token', 'credential', 'key', 'service_role', 'jwt'])
  )
);
CREATE INDEX IF NOT EXISTS idx_audit_events_org ON public.audit_events(organization_id, created_at DESC);
