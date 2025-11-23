
import json
import logging
import requests
from typing import Dict, Any, Optional

from config import (
    OLLAMA_GENERATE_ENDPOINT,
    OLLAMA_MODEL,
    SUPPORTED_INTENTS,
    CMD_UNKNOWN
)
from spotify_config import (
    SPOTIFY_ACTION_PLAY,
    SPOTIFY_ACTION_QUEUE,
    SPOTIFY_ACTION_SKIP_NEXT,
    SPOTIFY_ACTION_SKIP_PREVIOUS,
    SPOTIFY_ACTION_PAUSE,
    SPOTIFY_ACTION_RESUME
)

logger = logging.getLogger(__name__)
# --- UPDATED COMMAND_SCHEMA ---
COMMAND_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {
            "type": "string",
            "enum": SUPPORTED_INTENTS + [CMD_UNKNOWN],
            "description": "The user's intent classified into a specific category."
        },
        "query": {
            "type": "string",
            "description": "The actionable parameter for non-spotify intents (e.g., URL for website, search term for Netflix). For 'spotify' intent, this field may be absent or a generic term if a specific 'spotify_command' is provided."
        },
        "spotify_command": { # <--- NEW FIELD FOR SPOTIFY ACTIONS
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        SPOTIFY_ACTION_PLAY,
                        SPOTIFY_ACTION_QUEUE,
                        SPOTIFY_ACTION_SKIP_NEXT,
                        SPOTIFY_ACTION_SKIP_PREVIOUS,
                        SPOTIFY_ACTION_PAUSE,
                        SPOTIFY_ACTION_RESUME
                    ],
                    "description": "The specific Spotify action to perform."
                },
                "track_query": {
                    "type": "string",
                    "description": "The song or artist to play or queue (only for play/queue actions)."
                }
            },
            "required": ["action"],
            "description": "Details for a Spotify-related command. Only present if 'intent' is 'spotify'."
        }
    },
    "required": ["intent"] # 'query' is no longer universally required
}

# --- UPDATED SYSTEM PROMPT ---
SYSTEM_PROMPT = f"""
You are a command parsing AI.
Your task is to analyze the user's request and classify their intent.
Respond ONLY with a JSON object. Do NOT include any additional text or explanations.
The JSON object MUST conform to the following schema. For 'spotify' intent, ensure 'spotify_command' is correctly structured and 'query' may be omitted or generic.

Schema: {json.dumps(COMMAND_SCHEMA, indent=2)}

Example:
User: "play faded by alan walker on spotify"
Response: {{"intent": "spotify", "spotify_command": {{"action": "{SPOTIFY_ACTION_PLAY}", "track_query": "faded by alan walker"}}}}

Example:
User: "queue the next song from queen"
Response: {{"intent": "spotify", "spotify_command": {{"action": "{SPOTIFY_ACTION_QUEUE}", "track_query": "next song from queen"}}}}

Example:
User: "skip this song"
Response: {{"intent": "spotify", "spotify_command": {{"action": "{SPOTIFY_ACTION_SKIP_NEXT}"}}}}

Example:
User: "go to previous track"
Response: {{"intent": "spotify", "spotify_command": {{"action": "{SPOTIFY_ACTION_SKIP_PREVIOUS}"}}}}

Example:
User: "pause music"
Response: {{"intent": "spotify", "spotify_command": {{"action": "{SPOTIFY_ACTION_PAUSE}"}}}}

Example:
User: "resume playback"
Response: {{"intent": "spotify", "spotify_command": {{"action": "{SPOTIFY_ACTION_RESUME}"}}}}

Example:
User: "open youtube.com"
Response: {{"intent": "website", "query": "youtube.com"}}

Example:
User: "what is the weather like today?"
Response: {{"intent": "unknown", "query": "what is the weather like today?"}}
"""

def parse_command(user_input: str) -> Dict[str, Any]:
    """
    Sends user input to Ollama and parses the structured JSON response.
    
    Returns:
        dict: A dictionary with keys 'intent' and 'query'.
              Returns {'intent': 'unknown', 'query': ...} on failure.
    """
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": user_input,
        "system": SYSTEM_PROMPT,
        "format": "json",
        "stream": False,
        "options": {"temperature": 0.0}
    }

    try:
        logger.debug(f"Sending request to {OLLAMA_GENERATE_ENDPOINT}...")
        
        response = requests.post(
            OLLAMA_GENERATE_ENDPOINT, 
            json=payload, 
            headers={"Content-Type": "application/json"},
            timeout=10 
        )
        response.raise_for_status()

        api_response = response.json()
        llm_text_output = api_response.get("response", "").strip()

        # Removed the specific schema check, relying on json.loads and subsequent validation
        
        parsed_json = json.loads(llm_text_output)
        
        # Basic validation for the required 'intent' field
        if "intent" not in parsed_json:
            logger.error(f"LLM response missing 'intent' field: {llm_text_output}")
            return {"intent": CMD_UNKNOWN, "query": user_input}

        logger.info(f"Parsed Command: {parsed_json}")
        return parsed_json

    except json.JSONDecodeError:
        logger.error(f"LLM did not return valid JSON. Raw output: '{llm_text_output}'")
        return {"intent": CMD_UNKNOWN, "query": user_input}
        
    except requests.RequestException as e:
        logger.error(f"API connection failed: {e}")
        return {"intent": CMD_UNKNOWN, "query": "Connection Error"}