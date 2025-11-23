import os

# --- Spotify API Configuration ---
# You need to register your application on the Spotify Developer Dashboard
# (https://developer.spotify.com/dashboard/applications)
# and get your Client ID and Client Secret.
#
# IMPORTANT: The Redirect URI MUST EXACTLY match what you register in your
# Spotify Developer Dashboard settings.
# For local development, 'http://127.0.0.1:8888/callback' is a common choice.
#
# Environment variables are preferred for sensitive credentials.
# This MUST match the Redirect URI you set in your Spotify Developer Dashboard
SPOTIPY_REDIRECT_URI = os.getenv("SPOTIPY_REDIRECT_URI", "http://127.0.0.1:8888/callback")

# Scopes define what permissions your app requests from the user.
# These scopes allow reading playback state and controlling playback (play, pause, skip, queue).
SPOTIPY_SCOPE = (
    "user-read-playback-state "
    "user-modify-playback-state "
    "user-read-currently-playing "
    "app-remote-control " # Good to have for broader control
    "streaming" # Good to have for some playback scenarios
)

# Path to store the Spotify authentication token cache.
# This avoids needing to re-authenticate on every run.
SPOTIPY_CACHE_PATH = ".spotify_cache"

# --- Spotify Sub-commands/Actions ---
# These constants define the specific actions the LLM should classify for Spotify.
SPOTIFY_ACTION_PLAY = "play"
SPOTIFY_ACTION_QUEUE = "queue"
SPOTIFY_ACTION_SKIP_NEXT = "skip_next"
SPOTIFY_ACTION_SKIP_PREVIOUS = "skip_previous"
SPOTIFY_ACTION_PAUSE = "pause"
SPOTIFY_ACTION_RESUME = "resume"