"""EdgeErgo V3 — Database Migration Runner.

Executes ordered, timestamped SQL migrations from `supabase/migrations/`
and tracks applied versions in `public.schema_migrations`.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import psycopg


def get_migrations_dir() -> Path:
    """Returns the path to the supabase/migrations directory."""
    # From backend/app/db/migrations.py -> root -> supabase/migrations
    root = Path(__file__).resolve().parent.parent.parent.parent
    return root / "supabase" / "migrations"


def ensure_migration_table(conn: psycopg.Connection[tuple[object, ...]]) -> None:
    """Creates the migration tracking table if it does not exist."""
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS public.schema_migrations (
                version text PRIMARY KEY,
                applied_at timestamptz NOT NULL DEFAULT now()
            );
            """
        )
    conn.commit()


def get_applied_migrations(conn: psycopg.Connection[tuple[object, ...]]) -> set[str]:
    """Returns the set of migration versions that have already been applied."""
    ensure_migration_table(conn)
    with conn.cursor() as cur:
        cur.execute("SELECT version FROM public.schema_migrations;")
        rows = cur.fetchall()
        return {str(r[0]) for r in rows}


def apply_migration_file(conn: psycopg.Connection[tuple[object, ...]], file_path: Path) -> str:
    """Applies a single migration file transactionally."""
    ensure_migration_table(conn)
    version = file_path.name
    sql_content = file_path.read_text(encoding="utf-8")

    with conn.cursor() as cur:
        cur.execute(sql_content)
        cur.execute(
            "INSERT INTO public.schema_migrations (version) VALUES (%s);",
            (version,),
        )
    conn.commit()
    return version


def run_migrations(
    conn: psycopg.Connection[tuple[object, ...]],
    migrations_dir: Path | None = None,
) -> list[str]:
    """Discovers and applies all pending migrations in alphabetical order."""
    if migrations_dir is None:
        migrations_dir = get_migrations_dir()

    ensure_migration_table(conn)
    applied = get_applied_migrations(conn)

    migration_files = sorted(migrations_dir.glob("*.sql"))
    newly_applied: list[str] = []

    for file_path in migration_files:
        version = file_path.name
        if version not in applied:
            apply_migration_file(conn, file_path)
            newly_applied.append(version)

    return newly_applied
