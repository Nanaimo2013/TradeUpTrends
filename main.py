import json
import logging
import logging.config
import sys
from pathlib import Path
from scraper import Scraper
from console_ui import ConsoleUI
from trade_up_calculator import TradeUpCalculator
from temp import items_dict
import signal
from rich.traceback import install

# Install rich traceback handler
install(show_locals=True)

def setup_logging(config):
    """Configure logging based on config settings."""
    logging.config.dictConfig({
        'version': 1,
        'formatters': {
            'standard': {
                'format': config['logging']['format']
            },
        },
        'handlers': {
            'file': {
                'class': 'logging.FileHandler',
                'filename': config['logging']['file'],
                'formatter': 'standard',
            },
            'console': {
                'class': 'logging.StreamHandler',
                'formatter': 'standard',
            }
        },
        'loggers': {
            '': {
                'handlers': ['file', 'console'],
                'level': config['logging']['level'],
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

def signal_handler(signum, frame):
    """Handle interrupt signals gracefully."""
    print("\nGracefully shutting down...")
    sys.exit(0)

def analyze_market_data(items, config):
    """Analyze market data for trade-up opportunities."""
    if not items:
        return []
    
    opportunities = []
    min_price = config['analysis']['min_price']
    max_price = config['analysis']['max_price']
    min_profit = config['analysis']['min_profit_margin']
    
    for item in items:
        price = float(item['price'].replace('$', '').replace(',', ''))
        if min_price <= price <= max_price:
            potential_profit = ((max_price - price) / price) * 100
            if potential_profit >= min_profit:
                opportunities.append({
                    **item,
                    'potential_profit': potential_profit
                })
    
    return sorted(opportunities, key=lambda x: x['potential_profit'], reverse=True)

def main():
    # Set up signal handler for graceful exit
    signal.signal(signal.SIGINT, signal_handler)
    
    # Load configuration
    config = load_config()
    
    # Setup logging
    setup_logging(config)
    logger = logging.getLogger(__name__)
    
    try:
        # Initialize UI and tools
        ui = ConsoleUI()
        scraper = Scraper(config['scraping']['base_url'], items_dict)
        calculator = TradeUpCalculator(config)
        
        # Run the main UI loop
        ui.run()
        
    except Exception as e:
        logger.exception("An error occurred during execution")
        print(f"\nError: {str(e)}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nGracefully shutting down...")
        sys.exit(0)

if __name__ == "__main__":
    main()