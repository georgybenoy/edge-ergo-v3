# EdgeErgo V3 — Rollback & Recovery Guide

This guide details rollback strategies for both the Windows Edge Agent and the Hosted Backend API/Database in the event of an unexpected regression, migration issue, or deployment defect.

---

## 1. Windows Edge Agent Rollback

### Scenario A: Binary Regression with Unchanged SQLite Schema
If a newly deployed edge agent binary exhibits regressions (e.g. camera driver incompatibility or UI freeze) and no new SQLite migrations were applied:
1. **Stop the Process:**
   ```powershell
   Stop-Process -Name "edge-ergo" -Force
   ```
2. **Restore Previous Binaries:** Overwrite `C:\EdgeErgo\` with the previous stable version archive (e.g. `edge-ergo-v3.0.0-win64.zip`).
3. **Verify Local Database:**
   ```powershell
   .\edge-ergo.exe --version
   .\edge-ergo.exe --selftest
   ```
4. **Restart Agent:**
   ```powershell
   Start-Process ".\edge-ergo.exe"
   ```

### Scenario B: Binary Rollback with Applied Database Migration
If the newer agent applied an irreversible forward migration that the older binary cannot parse:
1. Restore the pre-upgrade backup created in `%LOCALAPPDATA%\EdgeErgo\edge_agent.db.bak`:
   ```powershell
   $AppDir = "$env:LOCALAPPDATA\EdgeErgo"
   Copy-Item -Path "$AppDir\edge_agent.db.bak" -Destination "$AppDir\edge_agent.db" -Force
   if (Test-Path "$AppDir\edge_agent.db-wal.bak") {
       Copy-Item -Path "$AppDir\edge_agent.db-wal.bak" -Destination "$AppDir\edge_agent.db-wal" -Force
   }
   ```
2. Revert the application binary to the previous release.
3. Start the agent. Any assessments generated during the rollback window will be re-synchronized from the restored queue state.

---

## 2. Hosted Backend API Rollback (Render)

If a backend release on Render introduces an unexpected defect:
1. **Render Dashboard Rollback:**
   - Navigate to the Render Dashboard > `edge-ergo-api` Web Service.
   - Go to the **Deploys** tab.
   - Identify the previous successful commit or release.
   - Click the three dots `...` next to the deployment and select **Rollback to this deploy**.
   - Render will redeploy the previous container image and switch traffic once `/health/ready` responds with HTTP 200.
2. **Zero Ingest Interruption:** Edge agents in the field will buffer incoming assessments in their local SQLite `sync_queue` during the short deployment transition and resume flushing automatically with exponential backoff.

---

## 3. Database Schema Rollback (Supabase / PostgreSQL)

Alembic migrations are designed to be forward-compatible. If an Alembic migration must be rolled back:
1. **Downgrade Alembic Revision:**
   ```powershell
   cd backend
   alembic downgrade -1
   ```
2. **Breaking Column Removals:** In accordance with continuous deployment best practices, database migrations never drop columns in the same release that frontend/edge code stops writing to them. Use expand-and-contract patterns to maintain compatibility during rollbacks.
