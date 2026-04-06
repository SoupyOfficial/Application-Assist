"""
db.py — SQLite application tracking database.

Logs every job application attempt with metadata for tracking,
analysis, and time-savings measurement.

Database file: applications.db (excluded from git, local only).

Schema:
  applications (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    date               TEXT NOT NULL,          -- ISO 8601 date: "2026-04-05"
    company            TEXT,                   -- Company name
    role               TEXT,                   -- Job title
    url                TEXT NOT NULL,          -- Application URL
    ats_platform       TEXT,                   -- greenhouse | lever | ashby | workday | generic
    mode               TEXT,                   -- fill_only | fill_and_pause | fill_review_submit_if_safe
    status             TEXT,                   -- filled | submitted | skipped | error
    time_saved_seconds INTEGER,                -- Estimated seconds saved vs manual
    notes              TEXT                    -- Free text notes
  )
"""

import sqlite3
from datetime import date
from pathlib import Path

DB_PATH = str(Path(__file__).resolve().parent.parent.parent / "applications.db")


def _get_connection() -> sqlite3.Connection:
    """Return a connection to the SQLite database with WAL mode."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def init_db():
    """
    Initialize the SQLite database and create the applications table if it
    doesn't already exist.

    Safe to call on every run — uses CREATE TABLE IF NOT EXISTS.
    """
    with _get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS applications (
                id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                date               TEXT NOT NULL,
                company            TEXT,
                role               TEXT,
                url                TEXT NOT NULL,
                ats_platform       TEXT,
                mode               TEXT,
                status             TEXT,
                time_saved_seconds INTEGER,
                notes              TEXT
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_applications_date ON applications(date)"
        )
        conn.commit()


def log_application(
    url: str,
    company: str = None,
    role: str = None,
    ats_platform: str = None,
    mode: str = None,
    status: str = "filled",
    time_saved_seconds: int = None,
    notes: str = None,
) -> int:
    """
    Log a job application to the database.

    Args:
        url:                The job application URL.
        company:            Company name (if known).
        role:               Job title (if known).
        ats_platform:       Detected ATS platform name.
        mode:               Submission mode used.
        status:             One of: "filled", "submitted", "skipped", "error".
        time_saved_seconds: Estimated seconds saved vs. filling manually.
        notes:              Any free-text notes about this application.

    Returns:
        The row ID of the inserted record.

    TODO: Consider extracting company/role from the page title or job listing
    metadata before calling this function, rather than relying on the adapter
    to pass them in.
    """
    today = date.today().isoformat()
    with _get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO applications
                (date, company, role, url, ats_platform, mode, status, time_saved_seconds, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (today, company, role, url, ats_platform, mode, status, time_saved_seconds, notes),
        )
        conn.commit()
        return cursor.lastrowid


def get_history(limit: int = 50) -> list:
    """
    Retrieve recent application history.

    Args:
        limit: Maximum number of records to return (most recent first).

    Returns:
        List of row dicts with all application fields.

    TODO: Add filtering options:
      - Filter by status, date range, company, ats_platform
      - Add aggregate stats: total applications, total time saved, success rate
    """
    with _get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT * FROM applications ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def get_stats() -> dict:
    """
    Return aggregate statistics from the application log.

    Returns:
        Dict with:
          {
            "total_applications": int,
            "submitted":          int,
            "total_time_saved_seconds": int,
            "by_platform":        dict  (platform → count),
          }

    TODO: Implement stats aggregation with SQL GROUP BY queries.
    """
    # TODO: Implement stats queries
    with _get_connection() as conn:
        total = conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0]
        submitted = conn.execute(
            "SELECT COUNT(*) FROM applications WHERE status = 'submitted'"
        ).fetchone()[0]
        time_saved = conn.execute(
            "SELECT COALESCE(SUM(time_saved_seconds), 0) FROM applications"
        ).fetchone()[0]

        platform_rows = conn.execute(
            "SELECT ats_platform, COUNT(*) FROM applications GROUP BY ats_platform"
        ).fetchall()
        by_platform = {row[0] or "unknown": row[1] for row in platform_rows}

    return {
        "total_applications": total,
        "submitted": submitted,
        "total_time_saved_seconds": time_saved,
        "by_platform": by_platform,
    }


def get_today_count() -> int:
    """Return the number of applications logged today."""
    today = date.today().isoformat()
    with _get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM applications WHERE date = ?", (today,)
        ).fetchone()
        return row[0]
