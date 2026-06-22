"""
Zintro — Flask app entry.

Routes:
  /                  — home dashboard
  /recently-played   — chronological history
  /top-tracks        — most-played
  /moods             — mood tabs
  /moods/<name>      — filtered tracks for mood
  /analytics         — heatmap + hour rhythm
  /discover          — Spotify recommendations
  /library           — saved tracks
  /login             — sign-in page

  /auth/google
  /auth/google/callback

  /auth/spotify
  /auth/spotify/callback

  /auth/demo
  /logout

  /api/predict-next
"""
import os, time, secrets, datetime as dt
from functools import wraps
from flask import (Flask, render_template, request, redirect, url_for,
                   session, jsonify, abort)
from dotenv import load_dotenv
from authlib.integrations.flask_client import OAuth

load_dotenv()

import db, mood, spotify_client as sp, seed

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", secrets.token_hex(16))

oauth = OAuth(app)

google = oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={
        "scope": "openid email profile"
    }
)

# ── one-time DB init + ensure a demo user exists - 
#    ye bakwas sahi karna hai abhi
db.init_db()


# ─────────────────── helpers ───────────────────
def current_user():
    uid = session.get("uid")
    return db.get_user(uid) if uid else None


def login_required(fn):
    @wraps(fn)
    def w(*a, **kw):
        if not current_user():
            return redirect(url_for("login"))
        return fn(*a, **kw)
    return w


@app.context_processor
def inject_globals():
    u = current_user()
    nav = [
        ("home",            "Home",            "◉"),
        ("recently_played", "Recently played", "↻"),
        ("top_tracks",      "Top tracks",      "★"),
        ("moods",           "By mood",         "◐"),
        ("analytics",       "Analytics",       "▤"),
        ("discover",        "Discover",        "✺"),
        ("library",         "Library",         "♡"),
    ]
    return dict(
        user=u,
        nav=nav,
        active=request.endpoint,
        spotify_ready=sp.is_configured(),
    )


# ─────────────────── auth ───────────────────
@app.route("/login")
def login():
    if current_user():
        return redirect(url_for("home"))
    return render_template("login.html",
                           spotify_ready=sp.is_configured())

@app.route("/auth/google")
def auth_google():

    redirect_uri = url_for(
        "auth_google_callback",
        _external=True
    )

    return google.authorize_redirect(
        redirect_uri
    )


@app.route("/auth/google/callback")
def auth_google_callback():

    token = google.authorize_access_token()

    user_info = token["userinfo"]

    uid = db.upsert_user(
        google_id=user_info["sub"],
        display_name=user_info.get("name", "Google User"),
        email=user_info.get("email"),
        avatar_url=user_info.get("picture"),
        is_demo=0
    )

    session["uid"] = uid

    return redirect(url_for("home"))

@app.route("/auth/spotify")
def auth_spotify():
    if not sp.is_configured():
        return redirect(url_for("auth_demo"))
    url, state = sp.build_auth_url()
    session["oauth_state"] = state
    return redirect(url)


@app.route("/auth/spotify/callback")
def auth_spotify_cb():
    if request.args.get("state") != session.get("oauth_state"):
        return "state mismatch", 400
    tok = sp.exchange_code(request.args.get("code", ""))
    if not tok:
        return "token exchange failed", 400
    me = sp.me(tok["access_token"]) or {}
    uid = db.upsert_user(
        spotify_id=me.get("id"),
        display_name=me.get("display_name") or "Spotify user",
        email=me.get("email"),
        avatar_url=(me.get("images") or [{}])[0].get("url"),
        access_token=tok["access_token"],
        refresh_token=tok.get("refresh_token"),
        token_expires_at=tok["expires_at"],
        is_demo=0,
    )
    session["uid"] = uid
    # one-shot import of recent history if possible
    _import_spotify_history(uid, tok["access_token"])
    return redirect(url_for("home"))


def _import_spotify_history(uid, token):
    try:
        rp = sp.recently_played(token, limit=50) or {}
        items = rp.get("items", []) or []
        if not items: return
        ids = [it["track"]["id"] for it in items if it.get("track")]
        af  = sp.audio_features(token, ids) or {}
        feat_by_id = {f["id"]: f for f in (af.get("audio_features") or []) if f}
        for it in items:
            t = it.get("track") or {}
            if not t: continue
            f = feat_by_id.get(t["id"]) or {}
            tid = db.upsert_track(
                spotify_id=t["id"], name=t["name"],
                artist=", ".join(a["name"] for a in t.get("artists", [])),
                album=(t.get("album") or {}).get("name"),
                genre=None, year=int(((t.get("album") or {}).get("release_date") or "0")[:4]) or None,
                tempo=f.get("tempo"), music_key=str(f.get("key")) if f.get("key") is not None else None,
                energy=f.get("energy"), valence=f.get("valence"),
                danceability=f.get("danceability"), acousticness=f.get("acousticness"),
                instrumentalness=f.get("instrumentalness"),
                duration_ms=t.get("duration_ms"),
                cover_url=(t.get("album", {}).get("images") or [{}])[0].get("url"),
            )
            m, _ = mood.detect(f)
            played_at = dt.datetime.fromisoformat(
                it["played_at"].replace("Z", "+00:00")).timestamp()
            db.record_play(uid, tid, played_at, m)
    except Exception as e:
        app.logger.warning("history import failed: %s", e)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ─────────────────── pages ───────────────────
@app.route("/")
@login_required
def home():
    uid = session["uid"]
    plays = db.recent_plays(uid, limit=80)
    moods = db.mood_distribution(uid)
    total = sum(m["n"] for m in moods) or 1
    mood_pct = [{"k": m["mood"], "v": round(m["n"]*100/total),
                 "hex": mood_lib(m["mood"])["hex"],
                 "say": mood_lib(m["mood"])["blurb"]}
                for m in moods]
    dom = mood.dominant(plays)
    queue = mood.predict_next(plays, dom)
    heat = db.heatmap(uid)
    return render_template("home.html",
                           plays=plays[:12],
                           top=db.top_tracks(uid, 8),
                           mood_pct=mood_pct,
                           dominant=dom,
                           queue=queue,
                           hour_hist=db.hour_histogram(uid),
                           heat=heat)


@app.route("/recently-played")
@login_required
def recently_played():
    return render_template("recently_played.html",
                           plays=db.recent_plays(session["uid"], limit=80))


@app.route("/top-tracks")
@login_required
def top_tracks():
    return render_template("top_tracks.html",
                           top=db.top_tracks(session["uid"], 30))


@app.route("/moods")
@app.route("/moods/<name>")
@login_required
def moods(name=None):
    uid = session["uid"]
    dist = db.mood_distribution(uid)
    if not name and dist:
        name = dist[0]["mood"]
    name = name or "wistful"
    return render_template(
        "moods.html",
        mood_list=mood.MOODS,
        mood_meta=mood.MOOD_META,
        dist={m["mood"]: m["n"] for m in dist},
        active_mood=name,
        tracks=db.tracks_for_mood(uid, name, limit=40),
    )


@app.route("/analytics")
@login_required
def analytics():
    uid = session["uid"]
    return render_template("analytics.html",
                           heat=db.heatmap(uid),
                           hour_hist=db.hour_histogram(uid),
                           genres=db.genre_breakdown(uid))


@app.route("/discover")
@login_required
def discover():
    uid = session["uid"]
    u = current_user()
    items = []
    if u and u["access_token"] and sp.is_configured():
        plays = db.recent_plays(uid, 5)
        seeds = [p["spotify_id"] for p in plays if p["spotify_id"]][:5]
        rec = sp.recommendations(u["access_token"], seed_tracks=seeds, limit=24) or {}
        items = rec.get("tracks", []) or []
    return render_template("discover.html",
                           items=items,
                           demo_pool=db.tracks_for_mood(uid, mood.dominant(db.recent_plays(uid, 200)), 24))


@app.route("/library")
@login_required
def library():
    uid = session["uid"]
    with db.connect() as c:
        rows = c.execute(
            """SELECT t.*, s.added_at FROM saved_tracks s
               JOIN tracks t ON t.id = s.track_id WHERE s.user_id=?
               ORDER BY s.added_at DESC""", (uid,)).fetchall()
    return render_template("library.html", tracks=rows)


# ─────────────────── API ───────────────────
@app.route("/api/predict-next")
@login_required
def api_predict_next():
    m = request.args.get("mood")
    plays = db.recent_plays(session["uid"], 200)
    return jsonify(mood.predict_next(plays, m))


# ─────────────────── util ───────────────────
def mood_lib(name):
    return mood.MOOD_META.get(name, {"hex": "#ff5a1f", "blurb": ""})


@app.template_filter("ts")
def fmt_ts(s):
    if not s: return ""
    try:
        d = dt.datetime.fromisoformat(str(s))
    except Exception:
        return str(s)
    now = dt.datetime.now()
    delta = now - d
    if delta.days >= 1:
        return d.strftime("%b %d · %H:%M")
    h, rem = divmod(delta.seconds, 3600)
    m = rem // 60
    if h: return f"{h}h ago"
    if m: return f"{m}m ago"
    return "just now"


@app.template_filter("dur")
def fmt_dur(ms):
    if not ms: return "—"
    s = int(ms) // 1000
    return f"{s//60}:{s%60:02d}"


if __name__ == "__main__":
    print("Spotify configured:", sp.is_configured())
    app.run(host="0.0.0.0", port=3000, debug=True)
