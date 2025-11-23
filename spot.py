import logging
import os
import webbrowser
import spotipy
from colorama import Fore, Style
from spotipy.oauth2 import SpotifyOAuth
import json
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())

# Import Spotify-specific configuration

from spotify_config import (
    SPOTIPY_REDIRECT_URI,
    SPOTIPY_SCOPE,
    SPOTIPY_CACHE_PATH,
    SPOTIFY_ACTION_PLAY,
    SPOTIFY_ACTION_QUEUE,
    SPOTIFY_ACTION_SKIP_NEXT,
    SPOTIFY_ACTION_SKIP_PREVIOUS,
    SPOTIFY_ACTION_PAUSE,
    SPOTIFY_ACTION_RESUME
)

SPOTIPY_CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID")
SPOTIPY_CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET")

logger = logging.getLogger("Spotify_Handler")

# Global Spotify client instance
sp = None
spotify_oauth = None

# Global settings file path (must match app.py)
SETTINGS_FILE = 'settings.json'

def load_settings():
    """Loads settings from JSON file."""
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'r') as f:
            return json.load(f)
    return {"default_play_behavior": "queue"} # Default if file doesn't exist

def init_spotify_oauth():
    """Initializes the SpotifyOAuth object."""
    global spotify_oauth
    spotify_oauth = SpotifyOAuth(
        client_id=SPOTIPY_CLIENT_ID,
        client_secret=SPOTIPY_CLIENT_SECRET,
        redirect_uri=SPOTIPY_REDIRECT_URI,
        scope=SPOTIPY_SCOPE,
        cache_path=SPOTIPY_CACHE_PATH,
        open_browser=False # We'll handle opening the browser manually for clarity
    )
    logger.info("SpotifyOAuth object initialized.")

def get_spotify_client() -> spotipy.Spotify | None:
    """
    Initializes and returns an authenticated Spotify client.
    Handles token caching and refresh.
    """
    global sp, spotify_oauth

    if spotify_oauth is None:
        init_spotify_oauth()

    # If sp is already initialized and likely authenticated, return it.
    # Note: spotipy handles token refresh automatically with get_access_token if cache_path is set.
    if sp:
        return sp

    token_info = spotify_oauth.get_cached_token()

    if not token_info:
        logger.info("No cached Spotify token found. Initiating authentication flow.")
        auth_url = spotify_oauth.get_authorize_url()
        print(f"\n{Fore.YELLOW}>> [Spotify Auth] Please open this URL in your browser to log in and authorize Spotify:")
        print(f"{Fore.CYAN}{Style.BRIGHT}{auth_url}{Style.RESET_ALL}")
        webbrowser.open(auth_url)
        
        print(f"{Fore.YELLOW}>> After authorizing, copy the full URL from your browser's address bar and paste it here:")
        redirected_url = input(f"{Fore.BLUE}Redirected URL > {Fore.RESET}").strip()
        
        try:
            # Attempt to parse the code from the redirected URL to get the token
            code = spotify_oauth.parse_response_code(redirected_url)
            token_info = spotify_oauth.get_access_token(code)
            logger.info("Spotify authentication successful!")
        except Exception as e:
            logger.error(f"Spotify authentication failed: {e}")
            print(f"{Fore.RED}Spotify authentication failed. Please ensure the Redirect URI is correct and you granted access.")
            return None
    
    # If token_info is still None after all attempts
    if not token_info:
        logger.error("Failed to get Spotify access token.")
        return None

    # Create the Spotify client instance
    sp = spotipy.Spotify(auth=token_info['access_token'])
    logger.info("Spotify client initialized successfully.")
    return sp

def get_active_device_id(sp_client: spotipy.Spotify) -> str | None:
    """
    Gets the ID of an active Spotify device. If none are active, prompts the user
    to select from available devices and transfers playback.
    """
    try:
        devices = sp_client.devices()
        active_devices = [d for d in devices['devices'] if d['is_active']]
        
        if active_devices:
            logger.debug(f"Found active Spotify device: {active_devices[0]['name']}")
            return active_devices[0]['id']
        elif devices['devices']:
            print(f"\n{Fore.YELLOW}>> No active Spotify device found. Available devices:")
            for i, device in enumerate(devices['devices']):
                print(f"   {i+1}. {device['name']} ({device['type']})")
            
            while True:
                try:
                    choice = input(f"{Fore.BLUE}Enter number of device to use (or 's' to skip): {Fore.RESET}").strip()
                    if choice.lower() == 's':
                        print(f"{Fore.YELLOW}Skipping Spotify action due to no device selection.")
                        return None
                    
                    device_index = int(choice) - 1
                    if 0 <= device_index < len(devices['devices']):
                        selected_device = devices['devices'][device_index]
                        logger.info(f"Selected Spotify device: {selected_device['name']}")
                        # Transfer playback to the selected device, but don't start playing yet
                        sp_client.transfer_playback(device_id=selected_device['id'], force_play=True)
                        return selected_device['id']
                    else:
                        print(f"{Fore.RED}Invalid choice. Please enter a valid number.")
                except ValueError:
                    print(f"{Fore.RED}Invalid input. Please enter a number or 's'.")
        else:
            print(f"{Fore.RED}No Spotify devices found. Please open Spotify on a device and ensure it's logged in.")
            logger.warning("No Spotify devices found.")
        
    except spotipy.exceptions.SpotifyException as e:
        logger.error(f"Spotify API error during device check: {e}")
        if "Invalid Access Token" in str(e) or "The access token expired" in str(e):
            print(f"{Fore.RED}Spotify Error: Access token expired. Please restart the app for re-authentication.")
            # Clear cache to force re-auth
            if os.path.exists(SPOTIPY_CACHE_PATH):
                os.remove(SPOTIPY_CACHE_PATH)
            global sp # Reset global client to force re-initialization
            sp = None
        else:
            print(f"{Fore.RED}An API error occurred while checking Spotify devices: {e}")
    except Exception as e:
        logger.error(f"General error in get_active_device_id: {e}")
        print(f"{Fore.RED}An unexpected error occurred while getting Spotify devices.")
    
    return None

def _handle_spotify_play_queue(sp_client: spotipy.Spotify, device_id: str, action: str, track_query: str):
    """Internal helper to handle play and queue actions."""
    results = sp_client.search(q=track_query, type='track', limit=1)
    if results and results['tracks']['items']:
        track = results['tracks']['items'][0]
        track_uri = track['uri']
        track_name = track['name']
        artist_name = track['artists'][0]['name']

        # Determine actual action based on intent and user setting
        final_action = action
        if action == SPOTIFY_ACTION_PLAY:
            settings = load_settings() # <--- LOAD SETTINGS
            if settings.get("default_play_behavior") == "queue":
                final_action = SPOTIFY_ACTION_QUEUE
                print(f"{Fore.YELLOW}   (Setting: 'Play' command interpreted as 'Add to Queue'.)")
            else:
                print(f"{Fore.YELLOW}   (Setting: 'Play' command interpreted as 'Play Directly'.)")
        
        if final_action == SPOTIFY_ACTION_QUEUE:
            sp_client.add_to_queue(uri=track_uri, device_id=device_id)
            print(f"{Fore.GREEN}   Action: Added '{track_name}' by {artist_name} to queue!")
        elif final_action == SPOTIFY_ACTION_PLAY: # This means it was either explicit PLAY or default was PLAY_DIRECT
            sp_client.start_playback(device_id=device_id, uris=[track_uri])
            print(f"{Fore.GREEN}   Action: Now playing '{track_name}' by {artist_name}!")
        
        # If it was a 'queue' action, check if playback should start.
        # If it was a 'play' action, we've already started.
        if final_action == SPOTIFY_ACTION_QUEUE:
            current_playback = sp_client.current_playback()
            if not current_playback or not current_playback.get('is_playing'):
                print(f"{Fore.GREEN}   Note: Music was paused, starting playback now.")
                sp_client.start_playback(device_id=device_id)
            else:
                print(f"{Fore.GREEN}   Note: Music is already playing. Track added to queue.")
    else:
        print(f"{Fore.YELLOW}   No Spotify track found for '{track_query}'.")

def _handle_spotify_skip(sp_client: spotipy.Spotify, device_id: str, action: str):
    """Internal helper to handle skip actions."""
    if action == SPOTIFY_ACTION_SKIP_NEXT:
        sp_client.next_track(device_id=device_id)
        print(f"{Fore.MAGENTA}   Action: Skipped to next track!")
    elif action == SPOTIFY_ACTION_SKIP_PREVIOUS:
        sp_client.previous_track(device_id=device_id)
        print(f"{Fore.MAGENTA}   Action: Skipped to previous track!")

def _handle_spotify_playback_control(sp_client: spotipy.Spotify, device_id: str, action: str):
    """Internal helper to handle pause/resume actions."""
    if action == SPOTIFY_ACTION_PAUSE:
        sp_client.pause_playback(device_id=device_id)
        print(f"{Fore.CYAN}   Action: Playback paused.")
    elif action == SPOTIFY_ACTION_RESUME:
        sp_client.start_playback(device_id=device_id)
        print(f"{Fore.CYAN}   Action: Playback resumed.")

def handle_spotify_command(command_data: dict):
    """
    Handles various Spotify commands based on the structured spotify_command.
    """
    logger.info(f"Handling Spotify command: {command_data}")
    print(f"\n{Fore.GREEN}{Style.BRIGHT}>> [SPOTIFY] 🎵{Style.RESET_ALL}")
    
    spotify_cmd_details = command_data.get("spotify_command")
    if not spotify_cmd_details:
        print(f"{Fore.RED}   Error: Missing 'spotify_command' details for Spotify intent.")
        return

    action = spotify_cmd_details.get("action")
    track_query = spotify_cmd_details.get("track_query")

    if not action:
        print(f"{Fore.RED}   Error: Spotify command missing 'action' field.")
        return

    sp_client = get_spotify_client()
    if not sp_client:
        print(f"{Fore.RED}   Spotify not connected. Cannot fulfill request.")
        return

    device_id = get_active_device_id(sp_client)
    if not device_id:
        print(f"{Fore.RED}   No suitable Spotify device found or selected. Cannot perform action '{action}'.")
        return

    try:
        if action in [SPOTIFY_ACTION_PLAY, SPOTIFY_ACTION_QUEUE]:
            if not track_query:
                print(f"{Fore.RED}   Error: '{action}' command requires a 'track_query'.")
                return
            _handle_spotify_play_queue(sp_client, device_id, action, track_query)
        elif action in [SPOTIFY_ACTION_SKIP_NEXT, SPOTIFY_ACTION_SKIP_PREVIOUS]:
            _handle_spotify_skip(sp_client, device_id, action)
        elif action in [SPOTIFY_ACTION_PAUSE, SPOTIFY_ACTION_RESUME]:
            _handle_spotify_playback_control(sp_client, device_id, action)
        else:
            print(f"{Fore.YELLOW}   Unknown Spotify action: '{action}'.")

    except spotipy.exceptions.SpotifyException as e:
        logger.error(f"Spotify API error: {e}")
        if "No active device found" in str(e):
            print(f"{Fore.RED}   Spotify Error: No active playback device found. Please start Spotify on a device first.")
        elif "Invalid Access Token" in str(e) or "The access token expired" in str(e):
            print(f"{Fore.RED}   Spotify Error: Access token expired. Attempting to re-authenticate on next command.")
            if os.path.exists(SPOTIPY_CACHE_PATH):
                os.remove(SPOTIPY_CACHE_PATH)
            global sp
            sp = None
        elif "Restriction violated" in str(e):
            print(f"{Fore.RED}   Spotify Error: Restriction violated. Ensure Spotify app is open on device '{device_id}' and you have permissions.")
        else:
            print(f"{Fore.RED}   Spotify API error: {e}")
    except Exception as e:
        logger.error(f"General error in Spotify handler: {e}")
        print(f"{Fore.RED}   An unexpected error occurred with Spotify.")