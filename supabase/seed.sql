-- EdgeErgo V3 — Development & Initial Seed Script
-- Source of Truth: docs/DECISIONS.md #1
-- Seeds ONE default organization for Release 1.
-- Contains NO fake users, NO fake assessments, and NO synthetic metrics.

INSERT INTO public.organizations (id, name, slug)
VALUES (
  '00000000-0000-0000-0000-000000000001',
  'Default Organization',
  'default-org'
)
ON CONFLICT (slug) DO UPDATE
SET name = EXCLUDED.name,
    updated_at = now();
