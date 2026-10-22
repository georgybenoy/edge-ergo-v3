"""Background synchronization worker coordinating queue drain, retries, and heartbeats."""

from __future__ import annotations

import logging
import random
import threading
import time

import httpx

from edge_ergo.overlay.presenter import OverlayPresenter
from edge_ergo.overlay.types import OverlayState
from edge_ergo.storage.credentials import (
    CredentialStore,
    get_global_credential_store,
    load_device_secret,
)
from edge_ergo.storage.repository import StorageRepository
from edge_ergo.sync.client import (
    DeviceAuthError,
    RateLimitedError,
    SyncClient,
    TransientNetworkError,
)
from edge_ergo.sync.payload import build_batch_payload

logger = logging.getLogger(__name__)


def compute_backoff_delay(
    attempt: int,
    base_delay: float = 2.0,
    max_delay: float = 300.0,
    max_exponent: int = 8,
    jitter_max: float = 3.0,
) -> float:
    """Calculates truncated exponential backoff with full uniform jitter."""
    exp = min(max(0, attempt), max_exponent)
    exponential = base_delay * (2.0**exp)
    delay = min(max_delay, exponential)
    jitter = random.uniform(0.0, jitter_max)
    return delay + jitter


class SyncWorker:
    """Crash-resilient background sync worker managing uploads, retries, and heartbeats."""

    def __init__(
        self,
        repository: StorageRepository,
        overlay_presenter: OverlayPresenter | None = None,
        credential_store: CredentialStore | None = None,
        sync_interval_s: float = 15.0,
        heartbeat_interval_s: float = 150.0,
        retention_interval_s: float = 86400.0,  # 24 hours
        batch_size: int = 50,
        lease_timeout_s: float = 60.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.repo = repository
        self.overlay_presenter = overlay_presenter
        self.credential_store = credential_store or get_global_credential_store()
        self.sync_interval_s = sync_interval_s
        self.heartbeat_interval_s = heartbeat_interval_s
        self.retention_interval_s = retention_interval_s
        self.batch_size = batch_size
        self.lease_timeout_s = lease_timeout_s
        self._http_client = http_client

        self._stop_event = threading.Event()
        self._worker_thread: threading.Thread | None = None
        self._lock = threading.Lock()

        self._last_heartbeat_time = 0.0
        self._last_retention_time = 0.0
        self._auth_halted = False

    def is_running(self) -> bool:
        return (
            self._worker_thread is not None
            and self._worker_thread.is_alive()
            and not self._stop_event.is_set()
        )

    def is_auth_halted(self) -> bool:
        return self._auth_halted

    def resume_auth(self) -> None:
        """Resets auth halt state, e.g. after re-enrollment."""
        with self._lock:
            self._auth_halted = False
            logger.info("Sync worker auth halt cleared.")

    def start(self) -> bool:
        """Starts the background synchronization worker thread."""
        with self._lock:
            if self.is_running():
                return True

            self._stop_event.clear()
            self._auth_halted = False

            # Recover any stale leases from previous crashed session
            try:
                self.repo.recover_stale_leases(timeout_seconds=self.lease_timeout_s)
            except Exception as exc:
                logger.error("Failed to recover stale leases during startup: %s", exc)

            self._worker_thread = threading.Thread(
                target=self._run_loop,
                name="EdgeErgoSyncWorker",
                daemon=True,
            )
            self._worker_thread.start()
            logger.info("EdgeErgo sync worker started.")
            return True

    def stop(self, timeout_s: float = 3.0) -> None:
        """Stops the sync worker thread gracefully."""
        self._stop_event.set()
        if self._worker_thread is not None and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=timeout_s)
            self._worker_thread = None
        logger.info("EdgeErgo sync worker stopped.")

    def _run_loop(self) -> None:
        """Periodic sync, heartbeat, and retention loop."""
        while not self._stop_event.is_set():
            loop_start = time.monotonic()

            try:
                # 1. Stale lease recovery
                self.repo.recover_stale_leases(timeout_seconds=self.lease_timeout_s)

                # 2. Sync step (if not auth halted)
                if not self._auth_halted:
                    self.step_sync()

                # 3. Heartbeat step
                if not self._auth_halted and (
                    time.monotonic() - self._last_heartbeat_time >= self.heartbeat_interval_s
                ):
                    self.step_heartbeat()

                # 4. Retention purge step
                if time.monotonic() - self._last_retention_time >= self.retention_interval_s:
                    self.step_retention()

            except Exception as exc:
                logger.error("Unexpected error in sync worker loop: %s", exc, exc_info=True)

            # Sleep until next check or stop signal
            elapsed = time.monotonic() - loop_start
            sleep_time = max(1.0, self.sync_interval_s - elapsed)
            if self._stop_event.wait(timeout=sleep_time):
                break

    def step_sync(self) -> int:
        """Executes a single queue drain iteration. Returns number of processed events."""
        identity = self.repo.get_device_identity()
        if identity is None:
            # Device not enrolled yet
            self._update_overlay(sync_text="Unenrolled", state=OverlayState.READY)
            return 0

        # Load device secret from OS Credential Manager
        secret = load_device_secret(identity.public_id, store=self.credential_store)
        if not secret:
            logger.error("Device identity exists in SQLite but secret is missing from OS vault!")
            self._auth_halted = True
            self._update_overlay(
                sync_text="Missing Credential",
                state=OverlayState.AUTH_ERROR,
                error_msg="Device credential missing from secure storage.",
            )
            return 0

        # Lease batch
        batch = self.repo.lease_batch(
            max_batch_size=self.batch_size,
            lease_timeout_seconds=self.lease_timeout_s,
        )
        queue_depth = self.repo.get_queue_depth()

        if not batch:
            # Nothing pending
            self._update_overlay(
                sync_text="Synced",
                queue_depth=queue_depth,
                state=OverlayState.ACTIVE,
            )
            return 0

        records = [rec for rec, _ in batch]
        items = [item for _, item in batch]
        batch_ids = [r.event_id for r in records]
        max_attempts = max(item.attempt_count for item in items)

        self._update_overlay(
            sync_text=f"Syncing ({len(batch_ids)})...",
            queue_depth=queue_depth,
            state=OverlayState.SYNCING,
        )

        client = SyncClient(
            api_base_url=identity.api_base_url,
            credential=secret,
            http_client=self._http_client,
        )

        try:
            payload = build_batch_payload(records)
            result = client.upload_batch(payload)

            acked_ids: list[str] = []
            for item_res in result.results:
                if item_res.status in ("accepted", "duplicate"):
                    acked_ids.append(item_res.event_id)
                elif item_res.status == "rejected":
                    reason = item_res.reason_code or "REJECTED_BY_SERVER"
                    self.repo.mark_dead(item_res.event_id, reason)

            if acked_ids:
                self.repo.ack_events(acked_ids)

            logger.info(
                "Batch sync completed: %d accepted, %d duplicates, %d rejected",
                result.total_accepted,
                result.total_duplicates,
                result.total_rejected,
            )

            new_depth = self.repo.get_queue_depth()
            self._update_overlay(
                sync_text="Synced",
                queue_depth=new_depth,
                state=OverlayState.ACTIVE,
            )
            return len(batch_ids)

        except DeviceAuthError as exc:
            logger.error("Hard authentication failure during sync upload: %s", exc)
            self._auth_halted = True
            # Reset leased items to pending so they are not lost
            self.repo.record_retry(batch_ids, "AUTH_ERROR", retry_delay_seconds=3600.0)
            self._update_overlay(
                sync_text="Auth Error",
                queue_depth=self.repo.get_queue_depth(),
                state=OverlayState.AUTH_ERROR,
                error_msg="Workstation authorization failed or device was revoked. Uploads paused.",
            )
            return 0

        except RateLimitedError as exc:
            delay = (
                exc.retry_after
                if exc.retry_after is not None
                else compute_backoff_delay(max_attempts)
            )
            logger.warning("Rate limit hit during sync; backing off for %.1fs", delay)
            self.repo.record_retry(batch_ids, "RATE_LIMITED", retry_delay_seconds=delay)
            self._update_overlay(
                sync_text="Rate Limited",
                queue_depth=self.repo.get_queue_depth(),
                state=OverlayState.OFFLINE,
                error_msg="Server ingestion throttled; backing off.",
            )
            return 0

        except TransientNetworkError as exc:
            delay = compute_backoff_delay(max_attempts)
            logger.warning("Transient sync network error: %s. Retrying in %.1fs", exc, delay)
            self.repo.record_retry(batch_ids, "NETWORK_ERROR", retry_delay_seconds=delay)
            self._update_overlay(
                sync_text="Offline",
                queue_depth=self.repo.get_queue_depth(),
                state=OverlayState.OFFLINE,
                error_msg="Network connection unavailable; queued locally.",
            )
            return 0

        finally:
            if self._http_client is None:
                client.close()

    def step_heartbeat(self) -> bool:
        """Sends a periodic heartbeat with device state and queue depth."""
        identity = self.repo.get_device_identity()
        if identity is None or self._auth_halted:
            return False

        secret = load_device_secret(identity.public_id, store=self.credential_store)
        if not secret:
            return False

        client = SyncClient(
            api_base_url=identity.api_base_url,
            credential=secret,
            http_client=self._http_client,
        )

        try:
            depth = self.repo.get_queue_depth()
            client.send_heartbeat(queue_depth=depth, state="active_tracking")
            self.repo.update_heartbeat_timestamp()
            self._last_heartbeat_time = time.monotonic()
            logger.debug(
                "Successfully transmitted heartbeat to %s (queue_depth=%d)",
                identity.api_base_url,
                depth,
            )
            return True
        except DeviceAuthError:
            self._auth_halted = True
            self._update_overlay(
                sync_text="Auth Error",
                state=OverlayState.AUTH_ERROR,
                error_msg="Device revoked on heartbeat.",
            )
            return False
        except TransientNetworkError as exc:
            logger.debug("Transient failure on heartbeat: %s", exc)
            return False
        finally:
            if self._http_client is None:
                client.close()

    def step_retention(self) -> int:
        """Executes periodic guarded retention cleanup."""
        try:
            purged = self.repo.purge_retention(retention_days=90)
            self._last_retention_time = time.monotonic()
            return purged
        except Exception as exc:
            logger.error("Retention purge error: %s", exc)
            return 0

    def _update_overlay(
        self,
        sync_text: str,
        queue_depth: int | None = None,
        state: OverlayState | None = None,
        error_msg: str | None = None,
    ) -> None:
        """Safely updates overlay presenter state."""
        if self.overlay_presenter is None:
            return

        depth = queue_depth if queue_depth is not None else self.repo.get_queue_depth()
        vm = self.overlay_presenter.view_model
        new_state = state or vm.state

        # If current state is PAUSED or CAMERA_UNAVAILABLE, preserve camera state unless auth error
        if state == OverlayState.AUTH_ERROR:
            new_state = OverlayState.AUTH_ERROR
        elif vm.state in (OverlayState.PAUSED, OverlayState.CAMERA_UNAVAILABLE, OverlayState.ERROR):
            new_state = vm.state

        self.overlay_presenter.update_sync_status(
            sync_text=sync_text,
            queue_depth=depth,
            state=new_state,
            error_message=error_msg,
        )
