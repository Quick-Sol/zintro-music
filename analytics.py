"""
analytics.py
SQL-driven analytics on a user's listening behaviour.
"""

from database import get_connection


def listens_by_hour(user_id: int):
    """Return [(hour, count)] for every hour the user has played a song."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """SELECT hour_of_day AS hour, COUNT(*) AS plays
             FROM listening_history
            WHERE user_id = ?
            GROUP BY hour_of_day
            ORDER BY hour_of_day""",
        (user_id,),
    )
    rows = cur.fetchall()
    conn.close()
    return [(r["hour"], r["plays"]) for r in rows]


def peak_listening_hours(user_id: int, top_n: int = 3):
    """The hours during which the user listens the most."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """SELECT hour_of_day AS hour, COUNT(*) AS plays
             FROM listening_history
            WHERE user_id = ?
            GROUP BY hour_of_day
            ORDER BY plays DESC, hour_of_day ASC
            LIMIT ?""",
        (user_id, top_n),
    )
    rows = cur.fetchall()
    conn.close()
    return [(r["hour"], r["plays"]) for r in rows]


def top_songs(user_id: int, limit: int = 5):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """SELECT s.title, s.artist, COUNT(*) AS plays
             FROM listening_history h
             JOIN songs s ON s.song_id = h.song_id
            WHERE h.user_id = ?
            GROUP BY h.song_id
            ORDER BY plays DESC, s.title ASC
            LIMIT ?""",
        (user_id, limit),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def top_moods(user_id: int, limit: int = 5):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """SELECT mood, COUNT(*) AS plays
             FROM listening_history
            WHERE user_id = ?
            GROUP BY mood
            ORDER BY plays DESC
            LIMIT ?""",
        (user_id, limit),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def song_play_times(user_id: int, song_title: str):
    """All hours at which the user has played a specific song."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """SELECT h.played_at, h.hour_of_day, h.day_of_week, h.mood
             FROM listening_history h
             JOIN songs s ON s.song_id = h.song_id
            WHERE h.user_id = ?
              AND LOWER(s.title) = LOWER(?)
            ORDER BY h.played_at DESC""",
        (user_id, song_title),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def render_hour_histogram(hour_counts):
    """ASCII bar chart of plays per hour."""
    if not hour_counts:
        return "  (no data yet)"
    max_plays = max(c for _, c in hour_counts)
    lines = []
    for hour, plays in hour_counts:
        bar = "#" * int(round((plays / max_plays) * 30))
        lines.append(f"  {hour:02d}:00  {bar} {plays}")
    return "\n".join(lines)
