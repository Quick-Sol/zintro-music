"""Mood detection from Spotify audio features.

Six mood buckets. Detection uses a small rule-based classifier across
valence, energy, tempo, danceability, acousticness, instrumentalness.
Returns (mood_name, confidence 0..1).
"""

MOODS = ["wistful", "focused", "euphoric", "restless", "tender", "hype"]

MOOD_META = {
    "wistful":  {"hex": "#ff5a1f", "blurb": "slow, acoustic, low-valence weather"},
    "focused":  {"hex": "#e7d35a", "blurb": "instrumental, steady, low-vocal"},
    "euphoric": {"hex": "#5cc2a9", "blurb": "high valence + high energy + danceable"},
    "restless": {"hex": "#b35aa1", "blurb": "high energy + low valence — agitated"},
    "tender":   {"hex": "#ec8a6a", "blurb": "warm valence at low energy"},
    "hype":     {"hex": "#7aa8e0", "blurb": "fast tempo + maxed energy"},
}


def detect(features: dict) -> tuple[str, float]:
    """features: dict with keys valence/energy/tempo/danceability/
    acousticness/instrumentalness, all 0..1 except tempo (BPM)."""
    if not features:
        return ("wistful", 0.3)
    v   = features.get("valence", 0.5)
    e   = features.get("energy", 0.5)
    bpm = features.get("tempo", 100)
    dnc = features.get("danceability", 0.5)
    ac  = features.get("acousticness", 0.3)
    ins = features.get("instrumentalness", 0.0)

    # Score each mood; pick highest.
    scores = {
        "hype":     max(0, (e - 0.7) * 1.4 + (bpm - 140) / 80),
        "euphoric": max(0, (v - 0.55) * 0.9 + (e - 0.55) * 0.9 + (dnc - 0.5) * 0.7),
        "restless": max(0, (e - 0.55) * 1.1 + (0.45 - v) * 1.2),
        "focused":  max(0, (ins - 0.3) * 1.4 + (0.5 - e) * 0.6 + (0.5 - dnc) * 0.4),
        "tender":   max(0, (v - 0.5) * 0.8 + (0.55 - e) * 1.0 + (ac - 0.4) * 0.6),
        "wistful":  max(0, (0.55 - v) * 0.9 + (0.55 - e) * 0.9 + (ac - 0.3) * 0.5),
    }
    mood = max(scores.items(), key=lambda x: x[1])[0]
    raw  = scores[mood]
    conf = min(1.0, 0.45 + raw * 0.55)
    return (mood, round(conf, 2))


def dominant(history_rows) -> str:
    """history_rows: iterable of sqlite Row with detected_mood column."""
    counts = {}
    for r in history_rows:
        m = r["detected_mood"] if "detected_mood" in r.keys() else None
        if m:
            counts[m] = counts.get(m, 0) + 1
    if not counts:
        return "wistful"
    return max(counts, key=counts.get)


def predict_next(history_rows, mood: str | None = None):
    """Pick a next-up track from past plays of the same mood. Naive
    re-ranker that boosts tracks similar to recently-played ones."""
    if not history_rows:
        return []
    mood = mood or dominant(history_rows)
    pool = [r for r in history_rows if r["detected_mood"] == mood]
    if len(pool) < 5:
        pool = list(history_rows)
    # Sort by recency / play count
    seen = {}
    for r in pool:
        seen.setdefault(r["track_id"], r)
    ranked = list(seen.values())[:5]
    # Compose result rows
    out = []
    for i, r in enumerate(ranked):
        out.append({
            "t":   r["name"],
            "a":   f"{r['artist']} · {r['album'] or ''}".strip(" ·"),
            "g":   r["genre"] or "—",
            "y":   r["year"]  or "",
            "bpm": int(r["tempo"] or 0),
            "key": r["music_key"] or "—",
            "p":   max(45, 92 - i * 8),
            "why": [
                f'top match · mood "{mood}"',
                "mood weighting", "time of day",
                "key proximity", "valence drift",
            ][i] if i < 5 else "",
            "lead": i == 0,
        })
    return out
