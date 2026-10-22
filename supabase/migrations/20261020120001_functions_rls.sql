-- EdgeErgo V3 — Migration 2: Helper Functions, Views, Grants, & RLS Policies
-- Version: 20261020120001
-- Source of Truth: PRD.md §8, TECH_STACK.md §4, docs/DECISIONS.md

-- ============================================================================
-- 1. SECURITY DEFINER Helper Functions
-- ============================================================================

CREATE OR REPLACE FUNCTION public.is_org_member(p_org_id uuid)
RETURNS boolean
LANGUAGE sql
SECURITY DEFINER
STABLE
SET search_path = public, pg_temp
AS $$
  SELECT EXISTS (
    SELECT 1 FROM public.organization_members
    WHERE organization_id = p_org_id
      AND user_id = auth.uid()
  );
$$;

CREATE OR REPLACE FUNCTION public.org_role(p_org_id uuid)
RETURNS text
LANGUAGE sql
SECURITY DEFINER
STABLE
SET search_path = public, pg_temp
AS $$
  SELECT role FROM public.organization_members
  WHERE organization_id = p_org_id
    AND user_id = auth.uid()
  LIMIT 1;
$$;

-- Automatic profile creation on auth.users insert (Supabase Auth Hook)
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
BEGIN
  INSERT INTO public.profiles (id, display_name, created_at, updated_at)
  VALUES (
    NEW.id,
    COALESCE(NEW.raw_user_meta_data->>'display_name', NEW.email),
    now(),
    now()
  )
  ON CONFLICT (id) DO NOTHING;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- Retention Purge Procedure (docs/DECISIONS.md #8)
CREATE OR REPLACE FUNCTION public.purge_expired_records(
  p_assessment_days integer DEFAULT 365,
  p_heartbeat_days integer DEFAULT 30,
  p_audit_days integer DEFAULT 365
)
RETURNS TABLE (
  deleted_assessments bigint,
  deleted_heartbeats bigint,
  deleted_audit_events bigint
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
  v_assessments bigint;
  v_heartbeats bigint;
  v_audit bigint;
BEGIN
  WITH del_assessments AS (
    DELETE FROM public.assessment_events
    WHERE captured_at < (now() - (p_assessment_days || ' days')::interval)
    RETURNING 1
  )
  SELECT count(*) INTO v_assessments FROM del_assessments;

  WITH del_heartbeats AS (
    DELETE FROM public.device_heartbeats
    WHERE received_at < (now() - (p_heartbeat_days || ' days')::interval)
    RETURNING 1
  )
  SELECT count(*) INTO v_heartbeats FROM del_heartbeats;

  WITH del_audit AS (
    DELETE FROM public.audit_events
    WHERE created_at < (now() - (p_audit_days || ' days')::interval)
    RETURNING 1
  )
  SELECT count(*) INTO v_audit FROM del_audit;

  RETURN QUERY SELECT v_assessments, v_heartbeats, v_audit;
END;
$$;

-- ============================================================================
-- 2. Safe Views & Column Grants (Never expose credential_hash to reviewers)
-- ============================================================================

CREATE OR REPLACE VIEW public.devices_public
WITH (security_invoker = true) AS
SELECT
  id,
  organization_id,
  label,
  status,
  public_id,
  enrolled_at,
  revoked_at,
  last_seen_at,
  last_sync_at,
  agent_version,
  credential_version,
  created_at,
  updated_at
FROM public.devices;

-- ============================================================================
-- 3. Grants for Dedicated Backend Least-Privilege Role: edgeergo_api
-- ============================================================================

GRANT USAGE ON SCHEMA public TO edgeergo_api;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO edgeergo_api;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO edgeergo_api;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO edgeergo_api;

ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO edgeergo_api;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO edgeergo_api;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT EXECUTE ON FUNCTIONS TO edgeergo_api;

-- Grants for Supabase authenticated users (RLS will filter row access)
GRANT USAGE ON SCHEMA public TO authenticated;
GRANT SELECT ON public.organizations TO authenticated;
GRANT SELECT, UPDATE(display_name, updated_at) ON public.profiles TO authenticated;
GRANT SELECT ON public.organization_members TO authenticated;
-- Column-level grant on devices: authenticated users cannot read credential_hash
GRANT SELECT (
  id, organization_id, label, status, public_id, enrolled_at,
  revoked_at, last_seen_at, last_sync_at, agent_version, credential_version,
  created_at, updated_at
) ON public.devices TO authenticated;
GRANT SELECT ON public.devices_public TO authenticated;
GRANT SELECT ON public.device_enrollment_tokens TO authenticated;
GRANT SELECT ON public.assessment_events TO authenticated;
GRANT SELECT ON public.device_heartbeats TO authenticated;
GRANT SELECT ON public.audit_events TO authenticated;

-- Ensure anon has no table access whatsoever
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM anon;

-- ============================================================================
-- 4. Enable and FORCE Row Level Security (RLS) on All Tables
-- ============================================================================

ALTER TABLE public.organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.organizations FORCE ROW LEVEL SECURITY;

ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.profiles FORCE ROW LEVEL SECURITY;

ALTER TABLE public.organization_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.organization_members FORCE ROW LEVEL SECURITY;

ALTER TABLE public.devices ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.devices FORCE ROW LEVEL SECURITY;

ALTER TABLE public.device_enrollment_tokens ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.device_enrollment_tokens FORCE ROW LEVEL SECURITY;

ALTER TABLE public.assessment_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.assessment_events FORCE ROW LEVEL SECURITY;

ALTER TABLE public.device_heartbeats ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.device_heartbeats FORCE ROW LEVEL SECURITY;

ALTER TABLE public.audit_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_events FORCE ROW LEVEL SECURITY;

-- ============================================================================
-- 5. RLS Policies: edgeergo_api Role (Backend Service Access)
-- ============================================================================

CREATE POLICY "edgeergo_api_all_organizations" ON public.organizations
  FOR ALL TO edgeergo_api USING (true) WITH CHECK (true);

CREATE POLICY "edgeergo_api_all_profiles" ON public.profiles
  FOR ALL TO edgeergo_api USING (true) WITH CHECK (true);

CREATE POLICY "edgeergo_api_all_members" ON public.organization_members
  FOR ALL TO edgeergo_api USING (true) WITH CHECK (true);

CREATE POLICY "edgeergo_api_all_devices" ON public.devices
  FOR ALL TO edgeergo_api USING (true) WITH CHECK (true);

CREATE POLICY "edgeergo_api_all_tokens" ON public.device_enrollment_tokens
  FOR ALL TO edgeergo_api USING (true) WITH CHECK (true);

CREATE POLICY "edgeergo_api_all_assessments" ON public.assessment_events
  FOR ALL TO edgeergo_api USING (true) WITH CHECK (true);

CREATE POLICY "edgeergo_api_all_heartbeats" ON public.device_heartbeats
  FOR ALL TO edgeergo_api USING (true) WITH CHECK (true);

CREATE POLICY "edgeergo_api_all_audit" ON public.audit_events
  FOR ALL TO edgeergo_api USING (true) WITH CHECK (true);

-- ============================================================================
-- 6. RLS Policies: authenticated Users (Dashboard Read Access Only)
-- ============================================================================

-- Organizations: users read only organizations they belong to
CREATE POLICY "members_select_organization" ON public.organizations
  FOR SELECT TO authenticated
  USING (public.is_org_member(id));

-- Profiles: users read their own profile or fellow members in shared orgs
CREATE POLICY "users_select_profiles" ON public.profiles
  FOR SELECT TO authenticated
  USING (
    id = auth.uid()
    OR EXISTS (
      SELECT 1 FROM public.organization_members om_self
      JOIN public.organization_members om_target ON om_self.organization_id = om_target.organization_id
      WHERE om_self.user_id = auth.uid() AND om_target.user_id = public.profiles.id
    )
  );

CREATE POLICY "users_update_own_profile" ON public.profiles
  FOR UPDATE TO authenticated
  USING (id = auth.uid())
  WITH CHECK (id = auth.uid());

-- Organization Members: view members within their own orgs; NEVER insert/update/delete via client
CREATE POLICY "members_select_org_members" ON public.organization_members
  FOR SELECT TO authenticated
  USING (public.is_org_member(organization_id));

-- Devices: visible to members in the same organization
CREATE POLICY "members_select_devices" ON public.devices
  FOR SELECT TO authenticated
  USING (public.is_org_member(organization_id));

-- Enrollment Tokens: visible only to admins within the organization
CREATE POLICY "admins_select_tokens" ON public.device_enrollment_tokens
  FOR SELECT TO authenticated
  USING (
    public.is_org_member(organization_id)
    AND public.org_role(organization_id) = 'admin'
  );

-- Assessment Events: visible to members of the organization; client cannot mutate
CREATE POLICY "members_select_assessments" ON public.assessment_events
  FOR SELECT TO authenticated
  USING (public.is_org_member(organization_id));

-- Device Heartbeats: visible to members of the organization
CREATE POLICY "members_select_heartbeats" ON public.device_heartbeats
  FOR SELECT TO authenticated
  USING (public.is_org_member(organization_id));

-- Audit Events: visible only to admins within the organization
CREATE POLICY "admins_select_audit_events" ON public.audit_events
  FOR SELECT TO authenticated
  USING (
    public.is_org_member(organization_id)
    AND public.org_role(organization_id) = 'admin'
  );
