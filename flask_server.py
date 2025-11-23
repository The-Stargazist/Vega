# flask_server.py
import os
import json
import logging
from flask import Flask, render_template, redirect, request, session, url_for, jsonify
from spotipy.oauth2 import SpotifyOAuth
import spotipy

# Import Spotify config
from spotify_config import (
    SPOTIPY_CLIENT_ID,
    SPOTIPY_CLIENT_SECRET,
    SPOTIPY_REDIRECT_URI,
    SPOTIPY_SCOPE,
    SPOTIPY_CACHE_PATH,
    # These SPOTIFY_ACTION_* constants are no longer directly used in app.py's
    # frontend logic, but are still imported if any backend routes were to use them.
    SPOTIFY_ACTION_PLAY,
    SPOTIFY_ACTION_QUEUE,
    SPOTIFY_ACTION_SKIP_NEXT,
    SPOTIFY_ACTION_SKIP_PREVIOUS,
    SPOTIFY_ACTION_PAUSE,
    SPOTIFY_ACTION_RESUME
)

# Global settings file path (must match spotify_handler.py)
SETTINGS_FILE = 'settings.json'

def load_settings():
    """Loads settings from JSON file."""
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            logging.getLogger("Flask_App_Thread").error(f"Error decoding {SETTINGS_FILE}. Creating new default.")
            return {"default_play_behavior": "queue"}
    return {"default_play_behavior": "queue"}

def save_settings(settings):
    """Saves settings to JSON file."""
    try:
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(settings, f, indent=4)
        logging.getLogger("Flask_App_Thread").info(f"Settings saved to {SETTINGS_FILE}")
    except IOError as e:
        logging.getLogger("Flask_App_Thread").error(f"Error saving settings to {SETTINGS_FILE}: {e}")

def create_flask_app():
    """Factory function to create and configure the Flask app."""
    app = Flask(__name__)
    app.secret_key = os.getenv("FLASK_SECRET_KEY", "super_secret_dev_key")

    logger = logging.getLogger("Flask_App_Thread")
    
    # Initialize SpotifyOAuth for the web frontend
    sp_oauth_web = SpotifyOAuth(
        client_id=SPOTIPY_CLIENT_ID,
        client_secret=SPOTIPY_CLIENT_SECRET,
        redirect_uri=SPOTIPY_REDIRECT_URI,
        scope=SPOTIPY_SCOPE,
        cache_path=SPOTIPY_CACHE_PATH,
        open_browser=False
    )

    @app.route('/')
    def index():
        token_info = sp_oauth_web.get_cached_token()
        spotify_connected = token_info is not None and not sp_oauth_web.is_token_expired(token_info)
        
        current_track = None
        if spotify_connected:
            try:
                sp_client = spotipy.Spotify(auth=token_info['access_token'])
                playback = sp_client.current_playback()
                if playback and playback['item']:
                    current_track = {
                        'name': playback['item']['name'],
                        'artist': playback['item']['artists'][0]['name'] if playback['item']['artists'] else 'Unknown Artist',
                        'is_playing': playback['is_playing']
                    }
            except spotipy.exceptions.SpotifyException as e:
                logger.warning(f"Failed to get current playback info: {e}. Clearing cache if token expired.")
                if "Invalid Access Token" in str(e) or "The access token expired" in str(e):
                     if os.path.exists(SPOTIPY_CACHE_PATH):
                        os.remove(SPOTIPY_CACHE_PATH)
                        logger.info("Spotify cache cleared due to expired token.")
                spotify_connected = False
            except Exception as e:
                logger.error(f"Error fetching playback info: {e}")
                spotify_connected = False

        current_settings = load_settings() 

        return render_template(
            'index.html', 
            spotify_connected=spotify_connected,
            current_track=current_track,
            default_play_behavior=current_settings.get("default_play_behavior", "queue")
        )

    @app.route('/connect_spotify')
    def connect_spotify():
        auth_url = sp_oauth_web.get_authorize_url()
        return redirect(auth_url)

    @app.route('/callback')
    def callback():
        code = request.args.get('code')
        if code:
            try:
                token_info = sp_oauth_web.get_access_token(code)
                logger.info("Spotify token obtained and cached.")
                return redirect(url_for('index'))
            except Exception as e:
                logger.error(f"Error getting Spotify token: {e}")
                return f"Error getting token: {e}", 500
        return "No code received from Spotify.", 400

    @app.route('/disconnect_spotify')
    def disconnect_spotify():
        if os.path.exists(SPOTIPY_CACHE_PATH):
            os.remove(SPOTIPY_CACHE_PATH)
            logger.info("Spotify cache deleted.")
        return redirect(url_for('index'))

    @app.route('/set_play_behavior', methods=['POST'])
    def set_play_behavior():
        behavior = request.json.get('behavior')
        if behavior in ["play_direct", "queue"]:
            current_settings = load_settings()
            current_settings["default_play_behavior"] = behavior
            save_settings(current_settings)
            logger.info(f"Default play behavior set to: {behavior} and saved to {SETTINGS_FILE}")
            return jsonify({"success": True, "new_behavior": behavior})
        return jsonify({"success": False, "message": "Invalid behavior"}), 400

    @app.route('/spotify_action/<action_type>', methods=['POST'])
    def spotify_action(action_type):
        token_info = sp_oauth_web.get_cached_token()
        if not token_info or sp_oauth_web.is_token_expired(token_info):
            return jsonify({"success": False, "message": "Spotify not connected or token expired"}), 401
        
        try:
            sp_client = spotipy.Spotify(auth=token_info['access_token'])
            devices = sp_client.devices()
            active_device = next((d for d in devices['devices'] if d['is_active']), None)
            
            if not active_device and devices['devices']:
                sp_client.transfer_playback(device_id=devices['devices'][0]['id'], play=False)
                active_device = devices['devices'][0]
            
            if not active_device:
                return jsonify({"success": False, "message": "No active Spotify device found"}), 400
            
            device_id = active_device['id']

            if action_type == SPOTIFY_ACTION_PLAY:
                sp_client.start_playback(device_id=device_id)
                message = "Playback started/resumed."
            elif action_type == SPOTIFY_ACTION_PAUSE:
                sp_client.pause_playback(device_id=device_id)
                message = "Playback paused."
            elif action_type == SPOTIFY_ACTION_SKIP_NEXT:
                sp_client.next_track(device_id=device_id)
                message = "Skipped to next track."
            elif action_type == SPOTIFY_ACTION_SKIP_PREVIOUS:
                sp_client.previous_track(device_id=device_id)
                message = "Skipped to previous track."
            else:
                return jsonify({"success": False, "message": "Invalid Spotify action"}), 400
            
            return jsonify({"success": True, "message": message})

        except spotipy.exceptions.SpotifyException as e:
            logger.error(f"Spotify API error during action '{action_type}': {e}")
            if "Restriction violated" in str(e) or "No active device found" in str(e):
                 return jsonify({"success": False, "message": f"Spotify API error: Ensure Spotify app is open and playing on a device. ({e})"}), 403
            return jsonify({"success": False, "message": f"Spotify API error: {e}"}), 500
        except Exception as e:
            logger.error(f"Unexpected error in spotify_action: {e}")
            return jsonify({"success": False, "message": f"An unexpected error occurred: {e}"}), 500

    return app

# If flask_server.py is run directly, it will start the app
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    flask_app = create_flask_app()
    port = int(os.environ.get("FLASK_RUN_PORT", 8888))
    flask_app.run(debug=True, port=port)