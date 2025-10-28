import sqlite3
from contextlib import closing
from pathlib import Path
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, timezone

# Increment this number any time you change schema.
SCHEMA_VERSION = 2

DB_PATH = Path(__file__).parent / "stopwatch.db"  # anchored to repo

# --- DATABASE SETUP ---
# --- CONNECTION ---
@st.cache_resource
def get_conn(cache_buster: int = 0):
    # Use URI + mode=rw so we FAIL if the DB isn't present
    # (prevents SQLite from silently creating a blank DB).
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=rw", uri=True, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

def ensure_schema(conn):
    """Add new columns/tables here; safe to run every startup."""
    with closing(conn.cursor()) as cur:
        # Ensure base table exists
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS times (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                team TEXT NOT NULL,
                sprint_number INTEGER NOT NULL,
                time REAL NOT NULL,
                saved_at_date TEXT NOT NULL,
                saved_at_time TEXT NOT NULL
            )
            """
        )

        # Example migration: add a new column if it doesn't exist
        cur.execute("PRAGMA table_info(times)")
        existing_cols = {row[1] for row in cur.fetchall()}

        # --- add your new columns here ---
        # e.g. you added:  new_col TEXT
        if "new_col" not in existing_cols:
            cur.execute("ALTER TABLE times ADD COLUMN new_col TEXT")

        conn.commit()

def init_db():
    # bump SCHEMA_VERSION to force a fresh connection after schema changes
    conn = get_conn(cache_buster=SCHEMA_VERSION)
    ensure_schema(conn)

def get_next_sprint_number(username: str) -> int:
    conn = get_conn()
    today = datetime.now(timezone(timedelta(hours=-5))).date()
    with closing(conn.cursor()) as cur:
        cur.execute(
            """
            SELECT MAX(sprint_number)
            FROM times
            WHERE username = ?
              AND DATE(saved_at_date) = ?
        """,
            (username, today.isoformat()),
        )
        result = cur.fetchone()[0]
        return (result or 0) + 1


def save_time(username: str, team: str, time: float):
    sprint_number = get_next_sprint_number(username)
    conn = get_conn()
    with closing(conn.cursor()) as cur:
        cur.execute(
            """
            INSERT INTO times (username, team, sprint_number, time, saved_at_date, saved_at_time)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (
                username,
                team,
                sprint_number,
                time,
                datetime.now(timezone(timedelta(hours=-5))).date(),
                datetime.now(timezone(timedelta(hours=-5))).isoformat(),
            ),
        )
        conn.commit()


def load_times() -> pd.DataFrame:
    conn = get_conn()
    return pd.read_sql_query(
        """
        SELECT id, username, team, sprint_number, time, saved_at_date
        FROM times
        ORDER BY time ASC
        """,
        conn,
    )


def load_team_today(team: str) -> pd.DataFrame:
    conn = get_conn()
    return pd.read_sql_query(
        """
        SELECT id, username, team, sprint_number, time, saved_at_date
        FROM times
        WHERE team = ? AND DATE(saved_at_date) = DATE(?)
        """,
        conn,
        params=[team, datetime.now(timezone(timedelta(hours=-5))).date()],
    )


def delete_time(username: str, sprint_number: int):
    conn = get_conn()
    with closing(conn.cursor()) as cur:
        cur.execute("DELETE FROM times WHERE username = ? AND sprint_number = ?", (username, sprint_number))
        conn.commit()


def delete_time_by_ids(ids: list[int]) -> None:
    if not ids:
        return
    conn = get_conn()
    with closing(conn.cursor()) as cur:
        cur.executemany("DELETE FROM times WHERE id = ?", [(rid,) for rid in ids])
        conn.commit()


def insert_time(
    username: str, team: str, sprint_number: int, time_value: float, saved_at_date: str, saved_at_time: str
) -> None:
    if saved_at_date is None:
        saved_at_date = datetime.now(timezone(timedelta(hours=-5))).date()
        saved_at_time = datetime.now(timezone(timedelta(hours=-5))).isoformat()
    conn = get_conn()
    with closing(conn.cursor()) as cur:
        cur.execute(
            """
            INSERT INTO times (username, team, sprint_number, time, saved_at_date, saved_at_time)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (username.strip(), team, int(sprint_number), float(time_value), saved_at_date, saved_at_time),
        )
        conn.commit()


def update_time(row_id: int, username: str, sprint_number: int, time_value: float) -> None:
    conn = get_conn()
    with closing(conn.cursor()) as cur:
        cur.execute(
            """
            UPDATE times
            SET username = ?, sprint_number = ?, time = ?
            WHERE id = ?
            """,
            (username.strip(), int(sprint_number), float(time_value), int(row_id)),
        )
        conn.commit()
