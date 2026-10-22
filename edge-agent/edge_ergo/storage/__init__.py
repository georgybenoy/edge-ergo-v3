"""Storage subsystem for EdgeErgo V3 workstation agent."""

from edge_ergo.storage.credentials import (
    CredentialStore,
    KeyringCredentialStore,
    MemoryCredentialStore,
    delete_device_secret,
    get_global_credential_store,
    load_device_secret,
    save_device_secret,
    set_global_credential_store,
)
from edge_ergo.storage.database import Database, get_default_data_dir, get_default_db_path
from edge_ergo.storage.migrations import apply_migrations, get_current_schema_version
from edge_ergo.storage.repository import StorageRepository
from edge_ergo.storage.types import (
    AssessmentEventRecord,
    DeviceIdentity,
    SyncQueueItem,
    SyncQueueState,
    SyncStateInfo,
)

__all__ = [
    "AssessmentEventRecord",
    "CredentialStore",
    "Database",
    "DeviceIdentity",
    "KeyringCredentialStore",
    "MemoryCredentialStore",
    "StorageRepository",
    "SyncQueueItem",
    "SyncQueueState",
    "SyncStateInfo",
    "apply_migrations",
    "delete_device_secret",
    "get_current_schema_version",
    "get_default_data_dir",
    "get_default_db_path",
    "get_global_credential_store",
    "load_device_secret",
    "save_device_secret",
    "set_global_credential_store",
]
