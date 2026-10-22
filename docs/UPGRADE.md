# EdgeErgo V3 — Workstation Agent Upgrade Guide

This guide details the upgrade procedure for the EdgeErgo Windows Edge Agent, ensuring zero loss of pending offline assessment records and safe, forward-only SQLite database schema migrations.

---

## 1. Upgrade Invariants

1. **Local Database Preservation:** The agent's local SQLite database is stored in `%LOCALAPPDATA%\EdgeErgo\edge_agent.db`. It is **completely independent** of the application executable installation directory (`dist\edge-ergo\`). Upgrading the executable directory must **never** delete, overwrite, or reset `%LOCALAPPDATA%\EdgeErgo\`.
2. **Automatic Schema Migrations on Startup:** The agent database engine checks `schema_migrations` upon every launch. Unapplied migrations are automatically executed in an atomic transaction before any worker threads start.
3. **Pending Sync Queue Protection:** Any assessment records queued during an offline period remain in state `pending` or `in_flight` and will resume synchronization immediately after the upgrade.
4. **Preserved Scoped Credentials:** Device secrets stored in Windows Credential Manager are keyed by `edge-ergo:{public_id}` and survive binary upgrades without requiring re-enrollment.

---

## 2. Standard In-Place Binary Upgrade Procedure

### Step 1: Terminate the Running Agent
Exit EdgeErgo from the Windows System Tray, or terminate via PowerShell:
```powershell
Get-Process -Name "edge-ergo" -ErrorAction SilentlyContinue | Stop-Process -Force
```

### Step 2: Backup Local State (Precautionary)
Before replacing application files, create a backup snapshot of the local database:
```powershell
$AppDir = "$env:LOCALAPPDATA\EdgeErgo"
if (Test-Path "$AppDir\edge_agent.db") {
    Copy-Item -Path "$AppDir\edge_agent.db" -Destination "$AppDir\edge_agent.db.bak" -Force
    if (Test-Path "$AppDir\edge_agent.db-wal") {
        Copy-Item -Path "$AppDir\edge_agent.db-wal" -Destination "$AppDir\edge_agent.db-wal.bak" -Force
    }
}
```

### Step 3: Replace Executable Bundle
Replace the application directory with the new release files:
```powershell
# Extract new release bundle to destination (e.g. C:\Program Files\EdgeErgo or %LOCALAPPDATA%\Programs\EdgeErgo)
Expand-Archive -Path "edge-ergo-v3.1.0-win64.zip" -DestinationPath "C:\EdgeErgo" -Force
```

### Step 4: Run Database Smoke Verification
Verify the executable integrity and trigger migrations in self-test mode before full launch:
```powershell
C:\EdgeErgo\edge-ergo.exe --version
C:\EdgeErgo\edge-ergo.exe --selftest
```

### Step 5: Start the Upgraded Agent
Launch the application:
```powershell
Start-Process "C:\EdgeErgo\edge-ergo.exe"
```
The startup logs will confirm migration status:
```text
INFO: Database connected: C:\Users\user\AppData\Local\EdgeErgo\edge_agent.db
INFO: Current schema version: 1. Target schema version: 2.
INFO: Applying migration 002_add_index... Done.
INFO: Agent initialization complete. System tray active.
```

---

## 3. Enterprise Silent Upgrade via SCCM / Intune

For fleet-wide enterprise deployments:
1. Ensure the deployment package runs in user context (or accesses the targeted user's `%LOCALAPPDATA%` and Credential Manager scope).
2. The installation script must overwrite the binary bundle directory only.
3. Post-install launch command: `edge-ergo.exe --minimized`.
