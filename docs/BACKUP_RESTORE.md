# EdgeErgo V3 — Hosted Database Backup & Disaster Recovery Guide

This document defines the backup architecture, restore drill steps, and recovery expectations for EdgeErgo V3 hosted on Supabase (PRD §10, §12, §14).

---

## 1. Supabase Backup Architecture by Plan Tier

| Capability | Supabase Free Tier | Supabase Pro Tier | Enterprise Tier |
|---|:---:|:---:|:---:|
| **Automated Daily Backups** | Daily snapshots (7-day retention) | Daily snapshots (7-day retention) | Daily snapshots (30-day retention) |
| **Point-in-Time Recovery (PITR)** | Not Available | Optional Add-on (up to 7 days, 1-second granularity) | Included (up to 30 days) |
| **Manual Logical Backups (`pg_dump`)** | Available via CLI / connection pooler | Available via CLI / connection pooler | Available via CLI / connection pooler |
| **Storage Disaster Recovery** | Single-region AWS | Single-region AWS | Multi-region read replicas available |

> [!IMPORTANT]
> **Pilot Plan Recommendation:** For standard pilot validation on the Free/Pro plan, automated daily backups provide adequate coverage. For high-volume pilot deployments, enabling PITR (Point-in-Time Recovery) prevents data loss between daily snapshots.

---

## 2. What Is NOT Backed Up in the Database Snapshot

Administrators must be aware of elements excluded from standard database snapshots:
1. **Local Workstation SQLite Databases:** Records buffered on individual laptops before synchronization live solely on those machines. They are restored through edge queue re-synchronization, not database backups.
2. **Windows Credential Manager Secrets:** Local device secrets (`eed_*`) reside in OS DPAPI storage.
3. **Render Application Environment Variables:** Secrets configured in Render (`JWT_SECRET`, `SUPABASE_KEY`) must be stored in a secure credential vault (e.g. 1Password / Doppler / Bitwarden).
4. **Supabase Auth Config & Custom SMTP:** Project settings, OAuth client IDs, and email templates must be documented in Terraform / infrastructure-as-code or manual runbooks.

---

## 3. Manual Logical Backup Drill (`pg_dump`)

To execute an out-of-band manual backup prior to major schema migrations:

### Step 1: Export Schema and Data
Using the direct PostgreSQL connection URI (with `pg_dump` 15+):
```bash
pg_dump \
  --dbname="$SUPABASE_DB_URL" \
  --format=custom \
  --schema=public \
  --schema=auth \
  --file="edge_ergo_backup_$(date +%Y%m%d_%H%M%S).dump"
```

### Step 2: Verify Backup Integrity
Verify the archive table contents without restoring:
```bash
pg_restore --list edge_ergo_backup_*.dump | grep -E "organizations|devices|assessment_events"
```

---

## 4. Disaster Recovery & Restoration Drill Steps

### Scenario: Accidental Data Corruption or Catastrophic Tenant Drop

1. **Initiate Restore in Supabase Management Console:**
   - Log into `app.supabase.com` > Select EdgeErgo Project > **Database** > **Backups**.
   - Review available automated daily snapshots or PITR timeline.
   - Click **Restore to this point**.
   - *Note:* Supabase creates a new project or restores in-place depending on plan tier.
2. **Alternative: Restore from Custom Dump into Clean Database:**
   ```bash
   pg_restore \
     --clean \
     --if-exists \
     --no-owner \
     --no-privileges \
     --dbname="$NEW_SUPABASE_DB_URL" \
     edge_ergo_backup_20261020.dump
   ```
3. **Post-Restore Schema Verification:**
   - Run the automated database test suite against the restored database:
     ```bash
     python -m pytest backend/tests/test_db_rls.py -v
     python -m pytest tests/authz/test_authz_matrix.py -v
     ```
4. **Re-attach Render Web Service:**
   - If a new database project URL was generated, update `DATABASE_URL` in the Render Web Service environment settings and trigger a deployment.
5. **Edge Agent Self-Healing:**
   - Edge agents with unsynchronized assessment events will automatically resume sync. Any duplicate records will be gracefully marked `duplicate` without raising errors due to unique constraints on `event_id`.
