"""Spotify Web API client — OAuth (Authorization Code) + REST wrappers.

If SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET are unset the module still
imports; auth functions return None and callers should fall back to demo data.
"""
import os
import time
import base64
import secrets
import urllib.parse
import requests

CLIENT_ID     = os.getenv("SPOTIFY_CLIENT_ID", "").strip()
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "").strip()
REDIRECT_URI  = os.getenv("SPOTIFY_REDIRECT_URI",
                          "http://127.0.0.1:3000/auth/spotify/callback").strip()

SCOPES = " ".join([
    "user-read-email",
    "user-read-private",
    "user-read-recently-played",
    "user-top-read",
    "user-library-read",
    "user-read-playback-state",
])

AUTH_URL  = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
API_BASE  = "https://api.spotify.com/v1"


def is_configured() -> bool:
    return bool(CLIENT_ID and CLIENT_SECRET)


# ─────────────────── OAuth ───────────────────
def build_auth_url(state: str | None = None) -> str:
    state = state or secrets.token_urlsafe(16)
    qs = urllib.parse.urlencode({
        "client_id":     CLIENT_ID,
        "response_type": "code",
        "redirect_uri":  REDIRECT_URI,
        "scope":         SCOPES,
        "state":         state,
        "show_dialog":   "true",
    })
    return f"{AUTH_URL}?{qs}", state


def exchange_code(code: str) -> dict | None:
    if not is_configured():
        return None
    basic = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    r = requests.post(
        TOKEN_URL,
        headers={
            "Authorization": f"Basic {basic}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={
            "grant_type":   "authorization_code",
            "code":         code,
            "redirect_uri": REDIRECT_URI,
        },
        timeout=10,
    )
    if r.status_code != 200:
        return None
    j = r.json()
    j["expires_at"] = int(time.time()) + int(j.get("expires_in", 3600)) - 30
    return j


def refresh(refresh_token: str) -> dict | None:
    if not is_configured():
        return None
    basic = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    r = requests.post(
        TOKEN_URL,
        headers={
            "Authorization": f"Basic {basic}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={"grant_type": "refresh_token", "refresh_token": refresh_token},
        timeout=10,
    )
    if r.status_code != 200:
        return None
    j = r.json()
    j["expires_at"] = int(time.time()) + int(j.get("expires_in", 3600)) - 30
    return j


# ─────────────────── REST ───────────────────
def _get(path: str, token: str, **params):
    r = requests.get(
        f"{API_BASE}{path}",
        headers={"Authorization": f"Bearer {token}"},
        params=params,
        timeout=12,
    )
    if r.status_code == 401:
        return None
    r.raise_for_status()
    return r.json()


def me(token):                  return _get("/me", token)
def recently_played(token, limit=50):
    return _get("/me/player/recently-played", token, limit=limit)
def top_tracks(token, limit=25, time_range="medium_term"):
    return _get("/me/top/tracks", token, limit=limit, time_range=time_range)
def saved_tracks(token, limit=50):
    return _get("/me/tracks", token, limit=limit)
def audio_features(token, ids):
    if not ids: return {"audio_features": []}
    return _get("/audio-features", token, ids=",".join(ids))
def recommendations(token, seed_tracks=None, seed_genres=None,
                    target_valence=None, target_energy=None, limit=20):
    params = {"limit": limit}
    if seed_tracks: params["seed_tracks"] = ",".join(seed_tracks[:5])
    if seed_genres: params["seed_genres"] = ",".join(seed_genres[:5])
    if target_valence is not None: params["target_valence"] = target_valence
    if target_energy  is not None: params["target_energy"]  = target_energy
    return _get("/recommendations", token, **params)
