# Zintro — Terminal Music Recommendation App

Zintro is a small Python + SQLite app that:

1. Tracks each user's listening **history with mood**.
2. Provides **analytics** on *when* (hour of day, day of week) songs are
   played, both overall and for a specific song.
3. Predicts the **next song** for the user based on mood, time of day,
   and genre/artist affinity learned from history.

The whole app runs in your terminal — no servers, no extra dependencies
(only the Python standard library, which already ships with `sqlite3`).

## Files

| File              | Purpose                                              |
|-------------------|------------------------------------------------------|
| `zintro.py`       | Terminal entry point with a menu                     |
| `database.py`     | SQLite schema and CRUD helpers                       |
| `seed_data.py`    | Initial song catalogue (25 songs across 5 moods)     |
| `analytics.py`    | SQL queries for time/mood/song analytics             |
| `recommender.py`  | Weighted scoring model that predicts the next song   |

The database file `zintro.db` is created next to the scripts on first run.

## Database schema

```
users               (user_id, username, created_at)
songs               (song_id, title, artist, genre, mood, duration)
listening_history   (history_id, user_id, song_id, mood,
                     played_at, hour_of_day, day_of_week)
```

## How to run

From inside the `zintro/` folder:

```bash
python zintro.py
```

On first launch the catalogue is auto-seeded and you'll be asked for a
username (any string — a row is inserted for new users).

## Menu options

```
1) Browse / search songs               (filter by mood or genre)
2) Play a song                         (writes a row into listening_history)
3) View my listening history
4) Analytics: when do I listen?        (ASCII histogram of plays per hour)
5) Analytics: top songs, moods, peak hours
6) Analytics: when do I play a specific song?
7) Predict my next song                (mood-aware recommendation)
8) Add a new song to the catalogue
0) Quit
```

## How the prediction works

`recommender.predict_next` builds a per-user profile from
`listening_history` and scores every song the user hasn't heard recently:

| Signal                                      | Weight |
|---------------------------------------------|-------:|
| Matches the mood you entered now            |  3.0   |
| Matches the mood you usually play this hour |  2.0   |
| Genre share in your history                 |  2.0   |
| Artist share in your history                |  1.5   |
| Small global-popularity tie-breaker         |  0.3   |

The highest-scoring song is the predicted next song, and the reasons
behind the score are printed so the recommendation is explainable.

## Tips

* Play 5–10 songs first, then try option 7 — predictions improve fast.
* Option 4 only becomes interesting after you have plays across several
  hours of the day. To experiment quickly you can edit `played_at` /
  `hour_of_day` directly in `zintro.db` with any SQLite browser.
