"""
zintro.py
Terminal entry point for the Zintro music recommendation app.

Run:
    python zintro.py
"""

from datetime import datetime

import database as db
from seed_data import seed
from analytics import (
    listens_by_hour,
    peak_listening_hours,
    top_songs,
    top_moods,
    song_play_times,
    render_hour_histogram,
)
from recommender import predict_next


MOODS = ["Happy", "Sad", "Calm", "Energetic", "Focused"]


# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------

def banner():
    print()
    print("=" * 56)
    print("            ZINTRO  -  Music Recommendations")
    print("                 Python + SQLite Edition")
    print("=" * 56)


def menu():
    print()
    print("  1) Browse / search songs")
    print("  2) Play a song (logs to history)")
    print("  3) View my listening history")
    print("  4) Analytics: when do I listen?")
    print("  5) Analytics: top songs, moods, peak hours")
    print("  6) Analytics: when do I play a specific song?")
    print("  7) Predict my next song")
    print("  8) Add a new song to the catalogue")
    print("  0) Quit")


def ask(prompt, default=None):
    txt = f"  {prompt}"
    if default is not None:
        txt += f" [{default}]"
    txt += ": "
    value = input(txt).strip()
    return value if value else default


def pick_mood():
    print("  Moods: " + ", ".join(MOODS))
    while True:
        m = ask("Mood")
        if not m:
            return None
        for option in MOODS:
            if option.lower() == m.lower():
                return option
        print("    Please pick one of the listed moods.")


def print_songs(rows):
    if not rows:
        print("    (no matching songs)")
        return
    print(f"    {'ID':>4}  {'Title':<26} {'Artist':<22} {'Genre':<12} Mood")
    print("    " + "-" * 78)
    for r in rows:
        print(f"    {r['song_id']:>4}  {r['title'][:25]:<26} "
              f"{r['artist'][:21]:<22} {r['genre']:<12} {r['mood']}")


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------

def action_browse():
    print()
    mood = ask("Filter by mood (blank = any)", "")
    genre = ask("Filter by genre (blank = any)", "")
    rows = db.list_songs(mood=mood or None, genre=genre or None)
    print()
    print_songs(rows)


def action_play(user_id):
    print()
    rows = db.list_songs()
    print_songs(rows)
    print()
    sid = ask("Enter song ID to play")
    if not sid or not sid.isdigit():
        print("    Cancelled.")
        return
    song = db.get_song(int(sid))
    if not song:
        print("    No song with that ID.")
        return
    print(f"    Playing: '{song['title']}' by {song['artist']} "
          f"({song['genre']}, {song['mood']})")
    print(f"    Default mood tag for this play would be '{song['mood']}'.")
    mood = pick_mood() or song["mood"]
    db.log_play(user_id, song["song_id"], mood)
    print(f"    Logged at {datetime.now().strftime('%Y-%m-%d %H:%M')} "
          f"with mood '{mood}'.")


def action_history(user_id):
    print()
    rows = db.get_user_history(user_id, limit=25)
    if not rows:
        print("    No history yet. Play a song to build it.")
        return
    print(f"    {'Played at':<20} {'Hour':<5} {'Day':<10} "
          f"{'Mood':<10} {'Title':<22} Artist")
    print("    " + "-" * 90)
    for r in rows:
        print(f"    {r['played_at']:<20} {r['hour_of_day']:<5} "
              f"{r['day_of_week']:<10} {r['mood']:<10} "
              f"{r['title'][:21]:<22} {r['artist']}")


def action_when_listen(user_id):
    print()
    data = listens_by_hour(user_id)
    print("  Plays per hour of day:")
    print(render_hour_histogram(data))


def action_top(user_id):
    print()
    print("  Top songs:")
    for r in top_songs(user_id, 5):
        print(f"    - {r['title']} by {r['artist']}  ({r['plays']} plays)")
    print()
    print("  Top moods:")
    for r in top_moods(user_id, 5):
        print(f"    - {r['mood']}  ({r['plays']} plays)")
    print()
    print("  Peak listening hours:")
    for hour, plays in peak_listening_hours(user_id, 3):
        print(f"    - {hour:02d}:00  ({plays} plays)")


def action_when_song(user_id):
    print()
    title = ask("Song title")
    if not title:
        return
    rows = song_play_times(user_id, title)
    if not rows:
        print("    No plays of that song yet.")
        return
    print(f"  You played '{title}' {len(rows)} time(s):")
    for r in rows:
        print(f"    - {r['played_at']}  ({r['day_of_week']} "
              f"{r['hour_of_day']:02d}:00, mood={r['mood']})")


def action_predict(user_id):
    print()
    print("  Optional: tell me your current mood for a better pick.")
    mood = pick_mood()
    recs = predict_next(user_id, current_mood=mood, top_n=5)
    if not recs:
        print("    No recommendations available.")
        return
    print()
    print("  Predicted next songs (best first):")
    for i, (song, score, reason) in enumerate(recs, 1):
        print(f"   {i}. '{song['title']}' by {song['artist']} "
              f"[{song['genre']}, {song['mood']}]")
        print(f"      score={score:.2f}  -  {reason}")


def action_add_song():
    print()
    title = ask("Title")
    artist = ask("Artist")
    genre = ask("Genre", "Pop")
    mood = pick_mood() or "Happy"
    duration = ask("Duration (seconds)", "180")
    try:
        duration = int(duration)
    except ValueError:
        duration = 180
    sid = db.add_song(title, artist, genre, mood, duration)
    print(f"    Added song with id={sid}.")


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main():
    db.init_db()
    # Seed catalogue on first run
    if not db.list_songs():
        seed()

    banner()
    username = ask("Enter your username", "guest")
    user_id = db.get_or_create_user(username)
    print(f"  Welcome, {username}! (user_id={user_id})")

    actions = {
        "1": lambda: action_browse(),
        "2": lambda: action_play(user_id),
        "3": lambda: action_history(user_id),
        "4": lambda: action_when_listen(user_id),
        "5": lambda: action_top(user_id),
        "6": lambda: action_when_song(user_id),
        "7": lambda: action_predict(user_id),
        "8": lambda: action_add_song(),
    }

    while True:
        menu()
        choice = ask("Choose an option")
        if choice == "0":
            print("  Goodbye!")
            break
        action = actions.get(choice)
        if action:
            try:
                action()
            except KeyboardInterrupt:
                print("\n  (interrupted)")
            except Exception as exc:
                print(f"  Error: {exc}")
        else:
            print("  Unknown option.")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nGoodbye!")
