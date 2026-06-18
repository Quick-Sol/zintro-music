"""
seed_data.py
Populate the songs table with an initial catalogue.
"""

from database import add_song

SEED_SONGS = [
    # title, artist, genre, mood, duration_seconds
    ("Blinding Lights",     "The Weeknd",        "Pop",        "Happy",      200),
    ("Levitating",          "Dua Lipa",          "Pop",        "Happy",      203),
    ("Uptown Funk",         "Bruno Mars",        "Funk",       "Happy",      270),
    ("Happy",               "Pharrell Williams", "Pop",        "Happy",      232),
    ("Shape of You",        "Ed Sheeran",        "Pop",        "Happy",      233),

    ("Someone Like You",    "Adele",             "Soul",       "Sad",        285),
    ("Fix You",             "Coldplay",          "Rock",       "Sad",        295),
    ("Let Her Go",          "Passenger",         "Folk",       "Sad",        252),
    ("All of Me",           "John Legend",       "Soul",       "Sad",        269),
    ("Hurt",                "Johnny Cash",       "Country",    "Sad",        218),

    ("Weightless",          "Marconi Union",     "Ambient",    "Calm",       480),
    ("Clair de Lune",       "Debussy",           "Classical",  "Calm",       300),
    ("Holocene",            "Bon Iver",          "Indie",      "Calm",       337),
    ("River Flows in You",  "Yiruma",            "Classical",  "Calm",       189),
    ("Night Owl",           "Galimatias",        "Electronic", "Calm",       217),

    ("Lose Yourself",       "Eminem",            "Hip-Hop",    "Energetic",  326),
    ("Eye of the Tiger",    "Survivor",          "Rock",       "Energetic",  246),
    ("Stronger",            "Kanye West",        "Hip-Hop",    "Energetic",  311),
    ("Thunderstruck",       "AC/DC",             "Rock",       "Energetic",  292),
    ("Titanium",            "David Guetta",      "Electronic", "Energetic",  245),

    ("Bohemian Rhapsody",   "Queen",             "Rock",       "Focused",    354),
    ("Time",                "Hans Zimmer",       "Soundtrack", "Focused",    271),
    ("Experience",          "Ludovico Einaudi",  "Classical",  "Focused",    314),
    ("Strobe",              "Deadmau5",          "Electronic", "Focused",    634),
    ("Intro",               "The xx",            "Indie",      "Focused",    127),
]


def seed():
    for title, artist, genre, mood, dur in SEED_SONGS:
        add_song(title, artist, genre, mood, dur)
    print(f"Seeded {len(SEED_SONGS)} songs.")


if __name__ == "__main__":
    from database import init_db
    init_db()
    seed()
