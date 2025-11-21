from __future__ import annotations

import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from src.app.config import settings


def get_rate_limit_db_connection() -> sqlite3.Connection:
    """
    Get a writable SQLite connection for rate limiting operations.
    
    This is separate from the read-only connection used for SQL queries.
    """
    db_path = settings.sqlite_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_rate_limit_table() -> None:
    """
    Initialize the rate_limit table if it doesn't exist.
    
    This table tracks daily interactions per identifier (IP address or user ID).
    """
    conn = get_rate_limit_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rate_limit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                identifier TEXT NOT NULL,
                date TEXT NOT NULL,
                interaction_count INTEGER NOT NULL DEFAULT 0,
                last_interaction_at TEXT,
                UNIQUE(identifier, date)
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_rate_limit_identifier_date 
            ON rate_limit(identifier, date)
        """)
        conn.commit()
    finally:
        conn.close()


def get_daily_interaction_count(identifier: str) -> int:
    """
    Get the current interaction count for today for the given identifier.
    
    Args:
        identifier: IP address or user ID
        
    Returns:
        Current interaction count for today (0 if no record exists)
    """
    conn = get_rate_limit_db_connection()
    try:
        cursor = conn.cursor()
        today = date.today().isoformat()
        cursor.execute(
            "SELECT interaction_count FROM rate_limit WHERE identifier = ? AND date = ?",
            (identifier, today)
        )
        row = cursor.fetchone()
        return row[0] if row else 0
    finally:
        conn.close()


def increment_interaction_count(identifier: str) -> int:
    """
    Increment the interaction count for today for the given identifier.
    
    Creates a new record if one doesn't exist for today.
    
    Args:
        identifier: IP address or user ID
        
    Returns:
        New interaction count after increment
    """
    conn = get_rate_limit_db_connection()
    try:
        cursor = conn.cursor()
        today = date.today().isoformat()
        now = datetime.utcnow().isoformat()
        
        cursor.execute("""
            INSERT INTO rate_limit (identifier, date, interaction_count, last_interaction_at)
            VALUES (?, ?, 1, ?)
            ON CONFLICT(identifier, date) DO UPDATE SET
                interaction_count = interaction_count + 1,
                last_interaction_at = ?
        """, (identifier, today, now, now))
        
        conn.commit()
        
        cursor.execute(
            "SELECT interaction_count FROM rate_limit WHERE identifier = ? AND date = ?",
            (identifier, today)
        )
        row = cursor.fetchone()
        return row[0] if row else 0
    finally:
        conn.close()


def reset_daily_count(identifier: Optional[str] = None) -> int:
    """
    Reset interaction count for today.
    
    If identifier is provided, resets only for that identifier.
    If None, resets for all identifiers (admin operation).
    
    Args:
        identifier: Optional identifier to reset. If None, resets all.
        
    Returns:
        Number of records reset
    """
    conn = get_rate_limit_db_connection()
    try:
        cursor = conn.cursor()
        today = date.today().isoformat()
        
        if identifier:
            cursor.execute(
                "UPDATE rate_limit SET interaction_count = 0 WHERE identifier = ? AND date = ?",
                (identifier, today)
            )
        else:
            cursor.execute(
                "UPDATE rate_limit SET interaction_count = 0 WHERE date = ?",
                (today,)
            )
        
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def get_all_daily_counts(date_filter: Optional[str] = None) -> list[dict]:
    """
    Get all daily interaction counts (admin operation).
    
    Args:
        date_filter: Optional date filter (ISO format). If None, returns all records.
        
    Returns:
        List of dicts with identifier, date, interaction_count, last_interaction_at
    """
    conn = get_rate_limit_db_connection()
    try:
        cursor = conn.cursor()
        
        if date_filter:
            cursor.execute(
                "SELECT identifier, date, interaction_count, last_interaction_at FROM rate_limit WHERE date = ? ORDER BY identifier",
                (date_filter,)
            )
        else:
            cursor.execute(
                "SELECT identifier, date, interaction_count, last_interaction_at FROM rate_limit ORDER BY date DESC, identifier"
            )
        
        rows = cursor.fetchall()
        return [
            {
                "identifier": row["identifier"],
                "date": row["date"],
                "interaction_count": row["interaction_count"],
                "last_interaction_at": row["last_interaction_at"],
            }
            for row in rows
        ]
    finally:
        conn.close()

