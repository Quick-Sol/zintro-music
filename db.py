"""SQLite layer for Zintro.

Schema covers users, tracks, play history, mood snapshots, and
playlists. Designed to mirror what we'd actually persist from the
Spotify Web API responses.
"""
import sqlite3
import os
import time
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "zintro.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    spotify_id        TEXT UNIQUE,
    google_id         TEXT UNIQUE,
    display_name      TEXT NOT NULL,
    email             TEXT,
    avatar_url        TEXT,
    access_token      TEXT,
    refresh_token     TEXT,
    token_expires_at  INTEGER,
    is_demo           INTEGER DEFAULT 0,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tracks (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    spotify_id        TEXT UNIQUE,
    name              TEXT NOT NULL,
    artist            TEXT NOT NULL,
    album             TEXT,
    genre             TEXT,
    year              INTEGER,
    tempo             REAL,    -- BPM
    music_key         TEXT,
    energy            REAL,    -- 0..1
    valence           REAL,    -- 0..1
    danceability      REAL,
    acousticness      REAL,
    instrumentalness  REAL,
    duration_ms       INTEGER,
    preview_url       TEXT,
    cover_url         TEXT
);

CREATE TABLE IF NOT EXISTS play_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL,
    track_id        INTEGER NOT NULL,
    played_at       TIMESTAMP NOT NULL,
    detected_mood   TEXT,
    hour            INTEGER,         -- 0..23 (local)
    day_of_week     INTEGER,         -- 0=Mon..6=Sun
    FOREIGN KEY (user_id)  REFERENCES users(id),
    FOREIGN KEY (track_id) REFERENCES tracks(id)
);
CREATE INDEX IF NOT EXISTS idx_history_user_time
    ON play_history(user_id, played_at DESC);

CREATE TABLE IF NOT EXISTS saved_tracks (
    user_id   INTEGER NOT NULL,
    track_id  INTEGER NOT NULL,
    added_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, track_id)
);
"""


@contextmanager
def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with connect() as c:
        c.executescript(SCHEMA)


# ─────────────────── user helpers ───────────────────
def upsert_user(**fields) -> int:
    """Insert or update a user. Returns user id."""
    key = None
    for k in ("spotify_id", "google_id"):
        if fields.get(k):
            key = k
            break
    with connect() as c:
        if key:
            row = c.execute(
                f"SELECT id FROM users WHERE {key} = ?", (fields[key],)
            ).fetchone()
        else:
            row = None
        if row:
            uid = row["id"]
            sets = ", ".join(f"{k}=?" for k in fields)
            c.execute(f"UPDATE users SET {sets} WHERE id=?",
                      list(fields.values()) + [uid])
            return uid
        cols = ", ".join(fields.keys())
        qs = ", ".join("?" * len(fields))
        cur = c.execute(f"INSERT INTO users ({cols}) VALUES ({qs})",
                        list(fields.values()))
        return cur.lastrowid


def get_user(user_id: int):
    with connect() as c:
        return c.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()


# ─────────────────── track helpers ───────────────────
def upsert_track(**fields) -> int:
    with connect() as c:
        if fields.get("spotify_id"):
            row = c.execute(
                "SELECT id FROM tracks WHERE spotify_id=?",
                (fields["spotify_id"],),
            ).fetchone()
            if row:
                return row["id"]
        cols = ", ".join(fields.keys())
        qs = ", ".join("?" * len(fields))
        cur = c.execute(f"INSERT INTO tracks ({cols}) VALUES ({qs})",
                        list(fields.values()))
        return cur.lastrowid


def record_play(user_id: int, track_id: int, played_at: float,
                mood: str | None = None):
    import datetime as _dt
    dt = _dt.datetime.fromtimestamp(played_at)
    with connect() as c:
        c.execute(
            """INSERT INTO play_history
               (user_id, track_id, played_at, detected_mood, hour, day_of_week)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, track_id, dt.isoformat(), mood, dt.hour, dt.weekday()),
        )


# ─────────────────── analytics queries ───────────────────
def recent_plays(user_id: int, limit: int = 50):
    with connect() as c:
        return c.execute(
            """SELECT ph.*, t.name, t.artist, t.album, t.genre, t.year,
                      t.tempo, t.music_key, t.energy, t.valence,
                      t.cover_url, t.spotify_id
               FROM play_history ph JOIN tracks t ON t.id = ph.track_id
               WHERE ph.user_id=? ORDER BY ph.played_at DESC LIMIT ?""",
            (user_id, limit),
        ).fetchall()


def top_tracks(user_id: int, limit: int = 25):
    with connect() as c:
        return c.execute(
            """SELECT t.*, COUNT(ph.id) AS plays,
                      SUM(t.duration_ms) AS listen_ms
               FROM play_history ph JOIN tracks t ON t.id = ph.track_id
               WHERE ph.user_id=?
               GROUP BY t.id
               ORDER BY plays DESC LIMIT ?""",
            (user_id, limit),
        ).fetchall()


def mood_distribution(user_id: int):
    with connect() as c:
        return c.execute(
            """SELECT detected_mood AS mood, COUNT(*) AS n
               FROM play_history WHERE user_id=? AND detected_mood IS NOT NULL
               GROUP BY detected_mood ORDER BY n DESC""",
            (user_id,),
        ).fetchall()


def tracks_for_mood(user_id: int, mood: str, limit: int = 40):
    with connect() as c:
        return c.execute(
            """SELECT t.*, COUNT(ph.id) AS plays
               FROM play_history ph JOIN tracks t ON t.id = ph.track_id
               WHERE ph.user_id=? AND ph.detected_mood=?
               GROUP BY t.id ORDER BY plays DESC LIMIT ?""",
            (user_id, mood, limit),
        ).fetchall()


def hour_histogram(user_id: int):
    """24-bucket count of plays by local hour."""
    buckets = [0] * 24
    with connect() as c:
        for r in c.execute(
            "SELECT hour, COUNT(*) n FROM play_history WHERE user_id=? GROUP BY hour",
            (user_id,),
        ):
            buckets[r["hour"]] = r["n"]
    return buckets


def heatmap(user_id: int):
    """7×24 grid (day-of-week × hour) of play counts."""
    grid = [[0] * 24 for _ in range(7)]
    with connect() as c:
        for r in c.execute(
            """SELECT day_of_week, hour, COUNT(*) n FROM play_history
               WHERE user_id=? GROUP BY day_of_week, hour""",
            (user_id,),
        ):
            grid[r["day_of_week"]][r["hour"]] = r["n"]
    return grid


def genre_breakdown(user_id: int):
    with connect() as c:
        return c.execute(
            """SELECT COALESCE(t.genre,'Unknown') AS genre, COUNT(*) AS n
               FROM play_history ph JOIN tracks t ON t.id=ph.track_id
               WHERE ph.user_id=? GROUP BY t.genre ORDER BY n DESC""",
            (user_id,),
        ).fetchall()
