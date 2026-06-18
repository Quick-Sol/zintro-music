"""
recommender.py
Next-song prediction for Zintro.

Strategy (simple but explainable):
  Score every song the user has NOT already heard in the last
  `recent_window` plays. The score is a weighted sum of:

    * mood match with the user's *current* mood            (weight 3.0)
    * mood match with the user's most frequent mood at the
      current hour-of-day                                  (weight 2.0)
    * genre affinity (share of plays in that genre)        (weight 2.0)
    * artist affinity (share of plays by that artist)      (weight 1.5)
    * small popularity bonus (global play count)           (weight 0.3)

The highest-scoring song is the predicted "next" song.
"""

from collections import Counter
from datetime import datetime

from database import get_connection


# ---------------------------------------------------------------------------
# Profile building
# ---------------------------------------------------------------------------

def _user_profile(user_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """SELECT s.genre, s.artist, h.mood, h.hour_of_day, h.song_id
             FROM listening_history h
             JOIN songs s ON s.song_id = h.song_id
            WHERE h.user_id = ?""",
        (user_id,),
    )
    rows = cur.fetchall()
    conn.close()

    genre_counts = Counter(r["genre"] for r in rows)
    artist_counts = Counter(r["artist"] for r in rows)
    hour_mood = {}
    for r in rows:
        hour_mood.setdefault(r["hour_of_day"], Counter())[r["mood"]] += 1

    total = max(len(rows), 1)
    return {
        "total_plays":   total,
        "genre_share":   {g: c / total for g, c in genre_counts.items()},
        "artist_share":  {a: c / total for a, c in artist_counts.items()},
        "hour_mood":     hour_mood,
        "recent_song_ids": [r["song_id"] for r in rows[-10:]],
    }


def _global_popularity():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """SELECT song_id, COUNT(*) AS plays
             FROM listening_history
            GROUP BY song_id"""
    )
    pop = {r["song_id"]: r["plays"] for r in cur.fetchall()}
    conn.close()
    return pop


# ---------------------------------------------------------------------------
# Prediction
# ---------------------------------------------------------------------------

def predict_next(user_id: int, current_mood: str | None = None,
                 top_n: int = 5):
    """Return [(song_row, score, reason)] of recommended next songs."""
    profile = _user_profile(user_id)
    popularity = _global_popularity()
    hour = datetime.now().hour
    hour_mood_top = None
    if hour in profile["hour_mood"]:
        hour_mood_top = profile["hour_mood"][hour].most_common(1)[0][0]

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM songs")
    songs = cur.fetchall()
    conn.close()

    max_pop = max(popularity.values()) if popularity else 1
    scored = []

    for song in songs:
        if song["song_id"] in profile["recent_song_ids"]:
            # avoid immediate repeats
            continue

        score = 0.0
        reasons = []

        if current_mood and song["mood"].lower() == current_mood.lower():
            score += 3.0
            reasons.append(f"matches your '{current_mood}' mood")

        if hour_mood_top and song["mood"] == hour_mood_top:
            score += 2.0
            reasons.append(f"fits what you usually play at {hour:02d}:00")

        g_share = profile["genre_share"].get(song["genre"], 0)
        if g_share > 0:
            score += 2.0 * g_share
            reasons.append(f"you like {song['genre']}")

        a_share = profile["artist_share"].get(song["artist"], 0)
        if a_share > 0:
            score += 1.5 * a_share
            reasons.append(f"you've played {song['artist']} before")

        pop = popularity.get(song["song_id"], 0)
        score += 0.3 * (pop / max_pop)

        scored.append((song, score, "; ".join(reasons) or "exploration pick"))

    scored.sort(key=lambda x: x[1], reverse=True)

    # Cold start: nothing in history – fall back to mood / popularity
    if profile["total_plays"] == 0:
        fallback = []
        for song in songs:
            score = 0.0
            reasons = []
            if current_mood and song["mood"].lower() == current_mood.lower():
                score += 3.0
                reasons.append(f"matches your '{current_mood}' mood")
            score += 0.3 * (popularity.get(song["song_id"], 0) / max_pop)
            fallback.append((song, score,
                             "; ".join(reasons) or "popular starter"))
        fallback.sort(key=lambda x: x[1], reverse=True)
        return fallback[:top_n]

    return scored[:top_n]
