"""Storage repository implementing transactional SQLite queries and queue semantics."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

from edge_ergo.storage.database import Database
from edge_ergo.storage.types import (
    AssessmentEventRecord,
    DeviceIdentity,
    SyncQueueItem,
    SyncQueueState,
    SyncStateInfo,
)

logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    """Returns current UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


class StorageRepository:
    """Transactional repository managing device identity, telemetry events, and sync queue."""

    def __init__(self, db: Database) -> None:
        self.db = db

    # --- 1. Settings & Identity ---

    def get_setting(self, key: str) -> str | None:
        """Retrieves a persistent setting value by key."""
        row = self.db.fetchone("SELECT value FROM settings WHERE key = ?;", (key,))
        return str(row["value"]) if row else None

    def set_setting(self, key: str, value: str) -> None:
        """Saves or updates a setting value."""
        now_utc = _utc_now_iso()
        with self.db.transaction() as cur:
            cur.execute(
                """
                INSERT INTO settings (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at;
                """,
                (key, value, now_utc),
            )

    def get_device_identity(self) -> DeviceIdentity | None:
        """Loads registered device identity metadata. Secret is NOT stored here."""
        row = self.db.fetchone(
            """
            SELECT device_id, public_id, api_base_url, label, organization_id, enrolled_at
            FROM device_identity
            LIMIT 1;
            """
        )
        if not row:
            return None
        return DeviceIdentity(
            device_id=str(row["device_id"]),
            public_id=str(row["public_id"]),
            api_base_url=str(row["api_base_url"]),
            label=str(row["label"]),
            organization_id=str(row["organization_id"]),
            enrolled_at=str(row["enrolled_at"]),
        )

    def save_device_identity(self, identity: DeviceIdentity) -> None:
        """Atomically saves or updates device identity metadata."""
        with self.db.transaction() as cur:
            cur.execute("DELETE FROM device_identity;")
            cur.execute(
                """
                INSERT INTO device_identity (
                    device_id, public_id, api_base_url, label, organization_id, enrolled_at
                ) VALUES (?, ?, ?, ?, ?, ?);
                """,
                (
                    identity.device_id,
                    identity.public_id,
                    identity.api_base_url,
                    identity.label,
                    identity.organization_id,
                    identity.enrolled_at,
                ),
            )
        logger.info(
            "Saved device identity in SQLite (device_id=%s, public_id=%s)",
            identity.device_id,
            identity.public_id,
        )

    def delete_device_identity(self) -> None:
        """Removes local device identity."""
        with self.db.transaction() as cur:
            cur.execute("DELETE FROM device_identity;")
        logger.info("Deleted local device identity metadata.")

    # --- 2. Assessment Event Ingestion ---

    def enqueue_assessment_event(self, record: AssessmentEventRecord) -> None:
        """Atomically persists an assessment event and enqueues it for synchronization."""
        now_utc = _utc_now_iso()
        guidance_json = json.dumps(record.guidance_codes)

        with self.db.transaction() as cur:
            # 1. Insert assessment record
            cur.execute(
                """
                INSERT INTO assessment_events (
                    event_id, captured_at, scoring_method, scoring_version, validity,
                    score, neck_score, trunk_score, upper_arm_score,
                    postural_features, guidance_codes, software_version, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    record.event_id,
                    record.captured_at,
                    record.scoring_method,
                    record.scoring_version,
                    record.validity,
                    record.score,
                    record.neck_score,
                    record.trunk_score,
                    record.upper_arm_score,
                    record.postural_features,
                    guidance_json,
                    record.software_version,
                    record.created_at or now_utc,
                ),
            )

            # 2. Enqueue into sync_queue
            cur.execute(
                """
                INSERT INTO sync_queue (
                    event_id, state, attempt_count, next_attempt_at, last_error_code, leased_at
                ) VALUES (?, ?, 0, ?, NULL, NULL);
                """,
                (record.event_id, SyncQueueState.PENDING.value, now_utc),
            )

            # 3. Update queue depth cache
            cur.execute(
                """
                UPDATE sync_state
                SET queue_depth_cache = (
                    SELECT COUNT(*) FROM sync_queue WHERE state IN ('pending', 'in_flight')
                )
                WHERE id = 1;
                """
            )

    # --- 3. Queue Leasing, Acknowledgement, & Failure Handling ---

    def lease_batch(
        self,
        max_batch_size: int = 50,
        lease_timeout_seconds: float = 60.0,
    ) -> list[tuple[AssessmentEventRecord, SyncQueueItem]]:
        """Leases up to max_batch_size eligible pending or expired in_flight queue items."""
        now = datetime.now(timezone.utc)
        now_str = now.isoformat()
        lease_cutoff_str = (now - timedelta(seconds=lease_timeout_seconds)).isoformat()

        results: list[tuple[AssessmentEventRecord, SyncQueueItem]] = []

        with self.db.transaction() as cur:
            # Select eligible event_ids
            cur.execute(
                """
                SELECT event_id
                FROM sync_queue
                WHERE (state = 'pending' AND next_attempt_at <= ?)
                   OR (state = 'in_flight' AND leased_at <= ?)
                ORDER BY next_attempt_at ASC, rowid ASC
                LIMIT ?;
                """,
                (now_str, lease_cutoff_str, max_batch_size),
            )
            rows = cur.fetchall()
            if not rows:
                return []

            event_ids = [str(r["event_id"]) for r in rows]
            placeholders = ",".join("?" for _ in event_ids)

            # Mark them in_flight atomically
            cur.execute(
                f"""
                UPDATE sync_queue
                SET state = 'in_flight',
                    leased_at = ?,
                    attempt_count = attempt_count + 1
                WHERE event_id IN ({placeholders});
                """,
                (now_str, *event_ids),
            )

            # Fetch joined record data
            cur.execute(
                f"""
                SELECT 
                    e.event_id, e.captured_at, e.scoring_method, e.scoring_version, e.validity,
                    e.score, e.neck_score, e.trunk_score, e.upper_arm_score,
                    e.postural_features, e.guidance_codes, e.software_version, e.created_at,
                    q.state, q.attempt_count, q.next_attempt_at, q.last_error_code, q.leased_at
                FROM assessment_events e
                JOIN sync_queue q ON e.event_id = q.event_id
                WHERE e.event_id IN ({placeholders});
                """,
                tuple(event_ids),
            )

            record_map: dict[str, tuple[AssessmentEventRecord, SyncQueueItem]] = {}
            for row in cur.fetchall():
                try:
                    codes = json.loads(row["guidance_codes"])
                except Exception:
                    codes = []

                event_rec = AssessmentEventRecord(
                    event_id=str(row["event_id"]),
                    captured_at=str(row["captured_at"]),
                    scoring_method=str(row["scoring_method"]),
                    scoring_version=str(row["scoring_version"]),
                    validity=str(row["validity"]),
                    score=float(row["score"]) if row["score"] is not None else None,
                    neck_score=int(row["neck_score"]) if row["neck_score"] is not None else None,
                    trunk_score=int(row["trunk_score"]) if row["trunk_score"] is not None else None,
                    upper_arm_score=(
                        int(row["upper_arm_score"]) if row["upper_arm_score"] is not None else None
                    ),
                    postural_features=row["postural_features"],
                    guidance_codes=codes,
                    software_version=str(row["software_version"]),
                    created_at=str(row["created_at"]),
                )

                queue_item = SyncQueueItem(
                    event_id=str(row["event_id"]),
                    state=SyncQueueState(row["state"]),
                    attempt_count=int(row["attempt_count"]),
                    next_attempt_at=str(row["next_attempt_at"]),
                    last_error_code=row["last_error_code"],
                    leased_at=row["leased_at"],
                )

                record_map[str(row["event_id"])] = (event_rec, queue_item)

            for eid in event_ids:
                if eid in record_map:
                    results.append(record_map[eid])

        return results

    def ack_events(self, event_ids: list[str]) -> None:
        """Marks successfully delivered events as acked upon explicit server confirmation."""
        if not event_ids:
            return

        now_utc = _utc_now_iso()
        placeholders = ",".join("?" for _ in event_ids)

        with self.db.transaction() as cur:
            cur.execute(
                f"""
                UPDATE sync_queue
                SET state = 'acked',
                    leased_at = NULL
                WHERE event_id IN ({placeholders});
                """,
                tuple(event_ids),
            )

            # Update sync state and recalculate queue depth
            cur.execute(
                """
                UPDATE sync_state
                SET last_success_at = ?,
                    queue_depth_cache = (
                        SELECT COUNT(*) FROM sync_queue WHERE state IN ('pending', 'in_flight')
                    )
                WHERE id = 1;
                """,
                (now_utc,),
            )
        logger.debug("Acknowledged %d telemetry events in SQLite.", len(event_ids))

    def mark_dead(self, event_id: str, reason_code: str) -> None:
        """Permanently marks an event as dead (unretryable validation/server rejection)."""
        with self.db.transaction() as cur:
            cur.execute(
                """
                UPDATE sync_queue
                SET state = 'dead',
                    last_error_code = ?,
                    leased_at = NULL
                WHERE event_id = ?;
                """,
                (reason_code, event_id),
            )
            cur.execute(
                """
                UPDATE sync_state
                SET queue_depth_cache = (
                    SELECT COUNT(*) FROM sync_queue WHERE state IN ('pending', 'in_flight')
                )
                WHERE id = 1;
                """
            )
        logger.warning("Marked event_id: %s as DEAD (reason=%s)", event_id, reason_code)

    def record_retry(
        self,
        event_ids: list[str],
        error_code: str,
        retry_delay_seconds: float,
    ) -> None:
        """Returns in-flight events to pending status with a bounded backoff delay."""
        if not event_ids:
            return

        now = datetime.now(timezone.utc)
        next_attempt = (now + timedelta(seconds=retry_delay_seconds)).isoformat()
        placeholders = ",".join("?" for _ in event_ids)

        with self.db.transaction() as cur:
            cur.execute(
                f"""
                UPDATE sync_queue
                SET state = 'pending',
                    next_attempt_at = ?,
                    last_error_code = ?,
                    leased_at = NULL
                WHERE event_id IN ({placeholders});
                """,
                (next_attempt, error_code, *event_ids),
            )
        logger.debug(
            "Scheduled retry for %d events in %.1fs (code=%s)",
            len(event_ids),
            retry_delay_seconds,
            error_code,
        )

    def recover_stale_leases(self, timeout_seconds: float = 60.0) -> int:
        """Recovers abandoned in_flight queue items after an unexpected restart or crash."""
        now = datetime.now(timezone.utc)
        cutoff_str = (now - timedelta(seconds=timeout_seconds)).isoformat()
        now_str = now.isoformat()

        with self.db.transaction() as cur:
            cur.execute(
                """
                UPDATE sync_queue
                SET state = 'pending',
                    next_attempt_at = ?,
                    leased_at = NULL
                WHERE state = 'in_flight' AND leased_at <= ?;
                """,
                (now_str, cutoff_str),
            )
            recovered = cur.rowcount
            if recovered > 0:
                logger.info("Recovered %d stale in_flight sync leases.", recovered)
            return recovered

    # --- 4. Retention & Metrics ---

    def purge_retention(self, retention_days: int = 90) -> int:
        """Purges assessment events older than retention_days.

        Safety Invariant: Events with unacknowledged queue items (pending or in_flight)
        are NEVER deleted, ensuring zero offline telemetry loss regardless of age.
        """
        cutoff_str = (datetime.now(timezone.utc) - timedelta(days=retention_days)).isoformat()

        with self.db.transaction() as cur:
            cur.execute(
                """
                DELETE FROM assessment_events
                WHERE created_at < ?
                  AND event_id NOT IN (
                      SELECT event_id FROM sync_queue WHERE state != 'acked'
                  );
                """,
                (cutoff_str,),
            )
            purged = cur.rowcount
            if purged > 0:
                logger.info(
                    "Purged %d expired assessment events (> %d days)", purged, retention_days
                )
            return purged

    def get_queue_depth(self) -> int:
        """Returns the current number of pending and in_flight queue items."""
        row = self.db.fetchone(
            "SELECT COUNT(*) AS cnt FROM sync_queue WHERE state IN ('pending', 'in_flight');"
        )
        return int(row["cnt"]) if row else 0

    get_sync_queue_depth = get_queue_depth

    def get_events_by_state(self, state: SyncQueueState) -> list[SyncQueueItem]:
        """Returns all queue items matching the specified state, ordered by next_attempt_at."""
        with self.db.transaction() as cur:
            cur.execute(
                """
                SELECT event_id, state, attempt_count, next_attempt_at, last_error_code, leased_at
                FROM sync_queue
                WHERE state = ?
                ORDER BY next_attempt_at ASC;
                """,
                (state.value,),
            )
            return [
                SyncQueueItem(
                    event_id=str(row["event_id"]),
                    state=SyncQueueState(row["state"]),
                    attempt_count=int(row["attempt_count"]),
                    next_attempt_at=str(row["next_attempt_at"]),
                    last_error_code=row["last_error_code"],
                    leased_at=row["leased_at"],
                )
                for row in cur.fetchall()
            ]

    def get_sync_state(self) -> SyncStateInfo:
        """Returns cached sync status."""
        row = self.db.fetchone(
            """
            SELECT last_success_at, queue_depth_cache, last_heartbeat_at
            FROM sync_state WHERE id = 1;
            """
        )
        if not row:
            return SyncStateInfo(last_success_at=None, queue_depth=0, last_heartbeat_at=None)
        return SyncStateInfo(
            last_success_at=row["last_success_at"],
            queue_depth=int(row["queue_depth_cache"]),
            last_heartbeat_at=row["last_heartbeat_at"],
        )

    def update_heartbeat_timestamp(self, ts: str | None = None) -> None:
        """Updates last_heartbeat_at in sync_state."""
        ts_val = ts or _utc_now_iso()
        with self.db.transaction() as cur:
            cur.execute("UPDATE sync_state SET last_heartbeat_at = ? WHERE id = 1;", (ts_val,))
