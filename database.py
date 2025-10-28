import sqlite3
from contextlib import closing
from pathlib import Path
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, timezone

DB_PATH = Path(__file__).parent / "stopwatch.db"  # anchored to repo

# --- DATABASE SETUP ---
@st.cache_resource
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_db():
    conn = get_conn()
    with closing(conn.cursor()) as cur:
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
        conn.commit()


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
