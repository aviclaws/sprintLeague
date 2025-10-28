import sqlite3
from contextlib import closing
import streamlit as st
import pandas as pd
from datetime import datetime, timezone

# --- DATABASE SETUP ---
@st.cache_resource
def get_conn():
    conn = sqlite3.connect("stopwatch.db", check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

def init_db():
    conn = get_conn()
    with closing(conn.cursor()) as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS times (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                team TEXT NOT NULL,
                sprint_number INTEGER NOT NULL,
                time REAL NOT NULL,
                saved_at TEXT NOT NULL
            )
        """)
        # Helps prevent duplicate sprints per user/team/day (not required, but handy)
        cur.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS uniq_user_team_sprint_day
            ON times (username, team, sprint_number, DATE(saved_at));
        """)
        conn.commit()

def get_next_sprint_number(username: str) -> int:
    conn = get_conn()
    today = datetime.now(timezone.utc).date()
    with closing(conn.cursor()) as cur:
        cur.execute("""
            SELECT MAX(sprint_number)
            FROM times
            WHERE username = ?
              AND DATE(saved_at) = ?
        """, (username, today.isoformat()))
        result = cur.fetchone()[0]
        return (result or 0) + 1

def save_time(username: str, team: str, time: float):
    sprint_number = get_next_sprint_number(username)
    conn = get_conn()
    with closing(conn.cursor()) as cur:
        cur.execute("""
            INSERT INTO times (username, team, sprint_number, time, saved_at)
            VALUES (?, ?, ?, ?, ?)
        """, (username, team, sprint_number, time, datetime.now(timezone.utc).isoformat()))
        conn.commit()

def load_times() -> pd.DataFrame:
    conn = get_conn()
    return pd.read_sql_query(
        """
        SELECT id, username, team, sprint_number, time, saved_at
        FROM times
        ORDER BY time ASC
        """,
        conn
    )

def load_team_today(team: str) -> pd.DataFrame:
    conn = get_conn()
    return pd.read_sql_query(
        """
        SELECT id, username, team, sprint_number, time, saved_at
        FROM times
        WHERE team = ? AND DATE(saved_at) = DATE(?)
        """,
        conn,
        params=(team, datetime.now(timezone.utc).isoformat())
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

def insert_time(username: str, team: str, sprint_number: int, time_value: float, saved_at: str | None = None) -> None:
    if saved_at is None:
        saved_at = datetime.now(timezone.utc).isoformat()
    conn = get_conn()
    with closing(conn.cursor()) as cur:
        cur.execute(
            """
            INSERT INTO times (username, team, sprint_number, time, saved_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (username.strip(), team, int(sprint_number), float(time_value), saved_at),
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