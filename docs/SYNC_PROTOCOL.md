# EdgeErgo V3 — Offline Synchronization Protocol & State Machine

## 1. Overview & Architectural Guarantees

The EdgeErgo V3 synchronization subsystem provides resilient, crash-safe, and privacy-preserving telemetry transmission from on-device edge workstations to the hosted FastAPI / Supabase PostgreSQL backend.

### Core Guarantees:
1. **Zero Raw Media Exfiltration:** Telemetry payloads contain only aggregated, allowlisted posture metrics (RULA score, subscores, guidance codes, software version). Raw video frames, image buffers, and 33-point Cartesian landmark coordinates **never** enter the synchronization pipeline.
2. **Local Analysis Resiliency:** Workstation ergonomic evaluation continues completely uninterrupted during offline periods, network disconnections, server maintenance, or authentication lockout (FR-006).
3. **At-Least-Once Delivery with Server Idempotency:** Telemetry records are enqueued locally in SQLite before network transmission. Retries and retransmissions cannot create duplicates in PostgreSQL due to composite primary key uniqueness `(device_id, event_id)` and `ON CONFLICT DO NOTHING` ingestion.
4. **Explicit Acknowledgement Lifecycle:** Queue items are marked `acked` or pruned **only** after positive server confirmation (`status: "accepted"` or `status: "duplicate"`).
5. **Fail-Safe Credential Protection:** Device secrets (`eed_<public_id>.<secret>`) reside exclusively in Windows Credential Manager (via OS DPAPI / Credential Vault) and are never written to SQLite, configuration files, or logs.

---

## 2. State Machine

### 2.1 Sync Queue Item State Lifecycle

Every syncable observation progresses through a finite state machine inside local SQLite (`sync_queue` table):

```
                     [Event Recorded]
                            │
                            ▼
                     ┌──────────────┐
                     │   PENDING    │◄─────────────────┐
                     └──────┬───────┘                  │
                            │                          │
                 Lease batch│                          │ (Transient error,
                 for upload │                          │  backoff retry delay)
                            ▼                          │
                     ┌──────────────┐                  │
                     │  IN_FLIGHT   │──────────────────┤
                     └──────┬───────┘                  │
                            │                          │
               ┌────────────┴────────────┐             │
               │                         │             │
(Server confirms:          (Server confirms:           │
 "accepted" / "duplicate")  "rejected")                │
               │                         │             │
               ▼                         ▼             │
        ┌──────────────┐          ┌──────────────┐     │
        │    ACKED     │          │     DEAD     │     │
        └──────────────┘          └──────────────┘     │
        (Safe to prune)           (Permanent failure;  │
                                   never retried)      │
                                                       │
               [Worker Crash / Power Loss]             │
                            │                          │
                            ▼                          │
                     (Lease expired                    │
                      > 60 seconds)                    │
                            │                          │
                            └──────────────────────────┘
                              (Automatic Lease Recovery)
```

| State | Description | Next Action |
|---|---|---|
| `pending` | Observation stored; waiting for next attempt window (`next_attempt_at <= now()`). | Eligible to be leased by sync worker. |
| `in_flight` | Leased by sync worker for upload; protected by timestamp lease (`leased_at`). | Awaits HTTP response or lease timeout. |
| `acked` | Positive confirmation from server received (`accepted` or `duplicate`). | Permanently acknowledged; eligible for local retention pruning after 90 days. |
| `dead` | Permanent rejection by server (`rejected` with validation/schema failure). | Quarantined; error logged; never retried to prevent queue head-of-line blocking. |

---

## 3. Sequence Diagrams

### 3.1 Device Enrollment Handshake

```mermaid
sequenceDiagram
    autonumber
    actor Admin as Organization Admin
    participant Dash as Web Dashboard
    actor User as Workstation User
    participant Agent as Edge Agent (CLI/Overlay)
    participant WCM as Windows Credential Manager
    participant DB as Local SQLite
    participant API as Hosted FastAPI

    Admin->>Dash: Generate Single-Use Token (label, TTL=15m)
    Dash->>API: POST /api/v1/devices/enrollment-tokens
    API-->>Dash: 201 Created (eet_..., expires_at)
    Admin->>User: Transmit token out-of-band

    User->>Agent: edge-ergo enroll --api <url> --token eet_...
    Agent->>API: POST /api/v1/devices/enroll (token, label, agent_version)
    Note over API: Atomically consume token (hash check),<br/>create device row, issue credential
    API-->>Agent: 201 Created (device_id, public_id, credential, org_id)

    Agent->>WCM: Store secret in Credential Vault (service="edge_ergo_device", username=public_id)
    Agent->>DB: Store metadata in device_identity (device_id, public_id, api_base_url, org_id)
    Note over Agent: Plaintext credential zeroed from memory.<br/>NEVER written to disk or logs.
    Agent-->>User: Enrollment successful (Public ID: edp_...)
```

### 3.2 Telemetry Ingestion Loop & Idempotency

```mermaid
sequenceDiagram
    autonumber
    participant Engine as Scoring Engine
    participant DB as Local SQLite
    participant Sync as Sync Worker Thread
    participant WCM as Windows Credential Manager
    participant API as Hosted FastAPI
    participant PG as PostgreSQL (Supabase)

    Engine->>DB: enqueue_assessment_event(record)
    Note over DB: Atomic transaction:<br/>1. INSERT assessment_events<br/>2. INSERT sync_queue (state='pending')

    loop Every sync cycle (default 30s)
        Sync->>DB: lease_batch(max_batch_size=50, lease_timeout=60s)
        DB-->>Sync: Return batch of records (state updated to 'in_flight')
        Sync->>WCM: Load device secret for public_id
        Sync->>API: POST /api/v1/assessments/batch (Authorization: Bearer eed_..., events=[...])
        
        API->>PG: INSERT INTO assessment_events (...) ON CONFLICT (device_id, event_id) DO NOTHING
        PG-->>API: Rows inserted / conflict count
        API-->>Sync: 200 OK (results=[{event_id, status: accepted|duplicate|rejected}])
        
        alt Event accepted or duplicate
            Sync->>DB: ack_events([event_id]) (state='acked')
        else Event rejected
            Sync->>DB: mark_dead(event_id, reason_code) (state='dead')
        end
    end
```

### 3.3 Transient Network Failure & Bounded Backoff with Jitter

```mermaid
sequenceDiagram
    autonumber
    participant Sync as Sync Worker
    participant DB as Local SQLite
    participant API as Hosted FastAPI
    participant UI as Desktop Overlay

    Sync->>DB: lease_batch() -> in_flight
    Sync->>API: POST /api/v1/assessments/batch
    Note over API: Network Down / DNS Failure / 503 Unavailable
    API--xSync: ConnectError / Timeout / HTTP 503

    Note over Sync: Compute Bounded Exponential Backoff:<br/>delay = min(300, 2 * (2^attempts)) + jitter(0, 3)<br/>(If HTTP 429: honor Retry-After header)
    Sync->>DB: record_retry(batch_ids, error_code, delay_s)
    Note over DB: Reset items to 'pending',<br/>next_attempt_at = now() + delay_s,<br/>leased_at = NULL
    Sync->>UI: Update status: OFFLINE (queue_depth=N, error="Network unavailable")
```

### 3.4 Hard Revocation & Authorization Failure (401 / 403)

```mermaid
sequenceDiagram
    autonumber
    participant Sync as Sync Worker
    participant DB as Local SQLite
    participant API as Hosted FastAPI
    participant UI as Desktop Overlay

    Sync->>DB: lease_batch() -> in_flight
    Sync->>API: POST /api/v1/assessments/batch (Bearer eed_...)
    Note over API: Device status is 'revoked' or secret mismatched
    API-->>Sync: 401 Unauthorized (INVALID_CREDENTIALS)

    Note over Sync: HARD HALT TRIGGERED:<br/>1. Stop all outgoing HTTP uploads<br/>2. DO NOT mark items dead or delete them<br/>3. Keep data safely queued in SQLite
    Sync->>DB: Reset in-flight items to 'pending'
    Sync->>UI: Transition to AUTH_ERROR state<br/>"Device credential invalid or revoked."
```

---

## 4. Retry and Backoff Algorithm

Transient errors are handled using truncated exponential backoff with full jitter to avoid thundering-herd synchronization waves against the hosted API:

$$\text{Backoff}(a) = \min\left(T_{\max},\; T_{\text{base}} \times 2^{\min(a, a_{\max})}\right) + \text{random}(0, J)$$

Where:
- $T_{\text{base}} = 2.0\text{ seconds}$ (base delay)
- $T_{\max} = 300.0\text{ seconds}$ (maximum backoff ceiling: 5 minutes)
- $a_{\max} = 8$ (maximum exponent threshold)
- $J = 3.0\text{ seconds}$ (randomized uniform jitter)
- $a$ = consecutive attempt count for the batch.

### HTTP 429 Rate Limiting
When the server responds with `429 Too Many Requests` containing a `Retry-After: <seconds>` header, the worker parses the header integer and sets:
$$\text{delay} = \max(\text{Retry-After}, 5.0) + \text{random}(0, 2)$$
This explicitly respects backend rate limits.

---

## 5. Local Data Retention and Guarded Deletion

In accordance with PRD FR-034 and Decision 8:
- **Local Assessment History Window:** 90 days.
- **Guarded Purge Rule:** A periodic cleanup task runs every 24 hours executing:
  ```sql
  DELETE FROM assessment_events
  WHERE created_at < datetime('now', '-90 days')
    AND event_id NOT IN (
      SELECT event_id FROM sync_queue WHERE state != 'acked'
    );
  ```
- **Inviolable Invariant:** Unsynchronized observations (`state IN ('pending', 'in_flight')`) are **NEVER** purged regardless of age. If a workstation is offline for 6 months, its queued observations remain intact until connectivity is re-established.
