import json
import logging
import logging.config
import sys
from pathlib import Path
from console_ui import ConsoleUI

def setup_logging(config):
    """Configure logging based on config settings."""
    logging.config.dictConfig({
        'version': 1,
        'formatters': {
            'standard': {
                'format': config['logging']['settings']['format']
            },
        },
        'handlers': {
            'file': {
                'class': 'logging.FileHandler',
                'filename': config['logging']['settings']['file_path'],
                'formatter': 'standard',
            },
            'console': {
                'class': 'logging.StreamHandler',
                'formatter': 'standard',
            }
        },
        'loggers': {
            '': {
                'handlers': ['file', 'console'] if config['logging']['settings']['console_logging_enabled'] else ['file'],
                'level': config['logging']['settings']['level'],
            }
        }
    })

def load_config():
    """Load configuration from config.json."""
    try:
        with open('config.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print("Error: config.json not found!")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in config.json: {str(e)}")
        sys.exit(1)

def main():
    try:
        # Load configuration
        config = load_config()
        
        # Setup logging
        setup_logging(config)
        logger = logging.getLogger(__name__)
        
        try:
            # Initialize and run console UI
            ui = ConsoleUI(config)
            ui.run()
            
        except KeyboardInterrupt:
            print("\nProgram terminated by user.")
            sys.exit(0)
        except Exception as e:
            logger.exception("An error occurred during execution")
            print(f"\nError: {str(e)}")
            sys.exit(1)
            
    except Exception as e:
        print(f"\nFatal Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()