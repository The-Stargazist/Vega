import sys
import logging
import colorama
import webbrowser
from colorama import Fore, Style
import threading # <--- NEW IMPORT
import os # <--- NEW IMPORT for FLASK_SECRET_KEY

from config import (
    DEBUG_MODE,
    CMD_SPOTIFY,
    CMD_NETFLIX,
    CMD_WEBSITE,
    CMD_UNKNOWN,
)
from llm import parse_command
from spot import handle_spotify_command
from flask_server import create_flask_app # <--- NEW IMPORT

# --- Setup ---
colorama.init(autoreset=True)

# Configure logging for main app and separate for Flask app
logging.basicConfig(
    level=logging.DEBUG if DEBUG_MODE else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("MainApp")

# --- Action Handlers ---

def handle_netflix(command_data: dict):
    """Handles movie and TV show requests."""
    query = command_data.get("query", "Netflix search")
    print(f"\n{Fore.RED}{Style.BRIGHT}>> [NETFLIX] 🍿{Style.RESET_ALL}")
    print(f"{Fore.RED}   Action: Searching Netflix")
    print(f"{Fore.RED}   Target: '{query}'")
    webbrowser.open(f"https://www.netflix.com/search?q={query}")


def handle_website(command_data: dict):
    """Handles general URL opening."""
    query = command_data.get("query", "Website URL")
    print(f"\n{Fore.CYAN}{Style.BRIGHT}>> [BROWSER] 🌐{Style.RESET_ALL}")
    print(f"{Fore.CYAN}   Action: Opening Website")
    if not (query.startswith("http://") or query.startswith("https://")):
        query = "https://" + query
    print(f"{Fore.CYAN}   Target: '{query}'")
    webbrowser.open(query)


def handle_unknown(command_data: dict):
    """Handles unrecognized or generic commands."""
    query = command_data.get("query", "Unknown input")
    print(f"\n{Fore.YELLOW}{Style.BRIGHT}>> [SYSTEM] ⚠️{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}   Status: Command not recognized or unsupported.")
    print(f"{Fore.YELLOW}   Input was: '{query}'")

# --- Dispatcher Map ---
COMMAND_HANDLERS = {
    CMD_SPOTIFY: handle_spotify_command,
    CMD_NETFLIX: handle_netflix,
    CMD_WEBSITE: handle_website,
    CMD_UNKNOWN: handle_unknown
}

# Function to run the Flask app in a thread
def run_flask_app():
    # It's important to set the secret key here as well,
    # or ensure it's set in the environment before main.py runs.
    if "FLASK_SECRET_KEY" not in os.environ:
        os.environ["FLASK_SECRET_KEY"] = "super_secret_dev_key" # Fallback if not set externally
    
    # Ensure Flask port is set. Default to 8888 for consistency.
    port = int(os.environ.get("FLASK_RUN_PORT", 8888))
    
    flask_app_instance = create_flask_app()
    logger.info(f"Starting Flask app on http://127.0.0.1:{port}")
    # We use debug=False here because the main app might handle debugging
    # And we don't want Flask's reloader to interfere with threading.
    flask_app_instance.run(debug=False, port=port)

# --- Main CLI Loop ---
def run_cli():
    print(f"{Fore.MAGENTA}{Style.BRIGHT}==========================================")
    print(f"{Fore.MAGENTA}{Style.BRIGHT}   🤖 AI COMMAND ASSISTANT (Ollama & Spotify)       ")
    print(f"{Fore.MAGENTA}{Style.BRIGHT}==========================================")
    print(f"{Fore.WHITE}Type 'exit' or 'quit' to close.")

    # Start Flask app in a separate thread
    flask_thread = threading.Thread(target=run_flask_app, daemon=True) # daemon=True means thread exits when main app exits
    flask_thread.start()
    logger.info("Flask app thread started.")
    print(f"{Fore.GREEN}Access Spotify controls at http://127.0.0.1:{os.environ.get('FLASK_RUN_PORT', 8888)}{Style.RESET_ALL}")

    while True:
        try:
            user_input = input(f"\n{Fore.BLUE}{Style.BRIGHT}You > {Style.RESET_ALL}").strip()

            if not user_input:
                continue
            
            if user_input.lower() in ["exit", "quit"]:
                print(f"\n{Fore.MAGENTA}Shutting down. Goodbye!")
                # Stopping Flask thread explicitly is hard with Flask's run()
                # daemon=True helps, but for cleaner shutdown in more complex apps,
                # you'd use a different server like Waitress and manage its lifecycle.
                break

            command_data = parse_command(user_input)
            
            intent = command_data.get("intent", CMD_UNKNOWN)
            
            handler = COMMAND_HANDLERS.get(intent, handle_unknown)
            handler(command_data)

        except KeyboardInterrupt:
            print(f"\n\n{Fore.MAGENTA}Force Quit detected. Goodbye!")
            sys.exit(0)
        except Exception as e:
            logger.error(f"Critical Error in main loop: {e}")

if __name__ == "__main__":
    run_cli()