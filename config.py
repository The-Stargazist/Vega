import os

# --- Ollama Configuration ---
# The URL where your local Ollama instance is running (default is port 11434)
OLLAMA_BASE_URL = os.getenv("OLLAMA_API_URL", "http://localhost:11434")
OLLAMA_GENERATE_ENDPOINT = "http://localhost:11434/api/generate"


# Scopes define what your app is allowed to do.
# The model you want to use (ensure you have run 'ollama pull llama3' or similar)
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")

# --- Command Constants ---
# These are the specific labels we train the AI to recognize
CMD_SPOTIFY = "spotify"
CMD_NETFLIX = "netflix"
CMD_WEBSITE = "website"
CMD_UNKNOWN = "unknown"

# A list of valid intents for validation logic
SUPPORTED_INTENTS = [CMD_SPOTIFY, CMD_NETFLIX, CMD_WEBSITE]

# --- Debugging ---
# Set to True to see detailed logs, False for a clean output
DEBUG_MODE = True