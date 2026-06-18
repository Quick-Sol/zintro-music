"""
database.py
SQLite schema and helpers for the Zintro music recommendation app.
"""

import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "zintro.db")


def get_connection():
    """Return a SQLite connection with row-dict access."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db():
    """Create all tables if they don't already exist."""
    conn = get_connection()
    cur = conn.cursor()

    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id     INTEGER PRIMARY KEY AUTOINCREMENT,
            username    TEXT UNIQUE NOT NULL,
            created_at  TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS songs (
            song_id     INTEGER PRIMARY KEY AUTOINCREMENT,
            title       TEXT NOT NULL,
            artist      TEXT NOT NULL,
            genre       TEXT NOT NULL,
            mood        TEXT NOT NULL,
            duration    INTEGER NOT NULL DEFAULT 180,
            UNIQUE(title, artist)
        );

        CREATE TABLE IF NOT EXISTS listening_history (
            history_id  INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            song_id     INTEGER NOT NULL,
            mood        TEXT NOT NULL,
            played_at   TEXT NOT NULL,
            hour_of_day INTEGER NOT NULL,
            day_of_week TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (song_id) REFERENCES songs(song_id)
        );

        CREATE INDEX IF NOT EXISTS idx_history_user
            ON listening_history(user_id);
        CREATE INDEX IF NOT EXISTS idx_history_song
            ON listening_history(song_id);
        CREATE INDEX IF NOT EXISTS idx_history_hour
            ON listening_history(hour_of_day);
        """
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

def get_or_create_user(username: str) -> int:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users WHERE username = ?", (username,))
    row = cur.fetchone()
    if row:
        user_id = row["user_id"]
    else:
        cur.execute(
            "INSERT INTO users (username, created_at) VALUES (?, ?)",
            (username, datetime.now().isoformat(timespec="seconds")),
        )
        user_id = cur.lastrowid
        conn.commit()
    conn.close()
    return user_id


# ---------------------------------------------------------------------------
# Songs
# ---------------------------------------------------------------------------

def add_song(title: str, artist: str, genre: str, mood: str,
             duration: int = 180) -> int:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """INSERT OR IGNORE INTO songs (title, artist, genre, mood, duration)
           VALUES (?, ?, ?, ?, ?)""",
        (title, artist, genre, mood, duration),
    )
    conn.commit()
    cur.execute(
        "SELECT song_id FROM songs WHERE title = ? AND artist = ?",
        (title, artist),
    )
    song_id = cur.fetchone()["song_id"]
    conn.close()
    return song_id


def list_songs(mood: str | None = None, genre: str | None = None):
    conn = get_connection()
    cur = conn.cursor()
    sql = "SELECT * FROM songs WHERE 1=1"
    params: list = []
    if mood:
        sql += " AND LOWER(mood) = LOWER(?)"
        params.append(mood)
    if genre:
        sql += " AND LOWER(genre) = LOWER(?)"
        params.append(genre)
    sql += " ORDER BY artist, title"
    cur.execute(sql, params)
    rows = cur.fetchall()
    conn.close()
    return rows


def get_song(song_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM songs WHERE song_id = ?", (song_id,))
    row = cur.fetchone()
    conn.close()
    return row


# ---------------------------------------------------------------------------
# Listening history
# ---------------------------------------------------------------------------

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday",
             "Friday", "Saturday", "Sunday"]


def log_play(user_id: int, song_id: int, mood: str) -> None:
    now = datetime.now()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO listening_history
               (user_id, song_id, mood, played_at, hour_of_day, day_of_week)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            user_id,
            song_id,
            mood,
            now.isoformat(timespec="seconds"),
            now.hour,
            DAY_NAMES[now.weekday()],
        ),
    )
    conn.commit()
    conn.close()


def get_user_history(user_id: int, limit: int = 20):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """SELECT h.played_at, h.mood, h.hour_of_day, h.day_of_week,
                  s.title, s.artist, s.genre
             FROM listening_history h
             JOIN songs s ON s.song_id = h.song_id
            WHERE h.user_id = ?
            ORDER BY h.played_at DESC
            LIMIT ?""",
        (user_id, limit),
    )
    rows = cur.fetchall()
    conn.close()
    return rows
