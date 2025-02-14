import re
import time
import random
import requests
import bs4
import json
import logging
import pprint
import os
from pathlib import Path
from selenium import webdriver
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from typing import List, Dict, Any, Optional, Generator
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from collections import deque
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeRemainingColumn
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
import subprocess
import datetime

# Set up logging
logger = logging.getLogger(__name__)
console = Console()

class ScraperException(Exception):
    """Custom exception for scraper-related errors."""
    pass

class Scraper:
    def __init__(self, url: str, items_dict: Dict[str, str], driver=None):
        self.base_url = url
        self.items_dict = items_dict
        self.session = requests.Session()
        self.driver = driver  # Use existing driver if provided
        self.console = Console()
        
        # Set up logging directory
        self.logs_dir = Path("logs")
        self.logs_dir.mkdir(exist_ok=True)
        
        # Create a unique log file for this session
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.analysis_log_file = self.logs_dir / f"analysis_{timestamp}.log"
        
        # Set up file handler for analysis-specific logging
        self.analysis_logger = logging.getLogger("analysis")
        self.analysis_logger.setLevel(logging.DEBUG)
        
        file_handler = logging.FileHandler(self.analysis_log_file)
        file_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        self.analysis_logger.addHandler(file_handler)
        
        self.logger = logging.getLogger(__name__)
        self._cleanup_in_progress = False
        
        # Load configuration
        try:
            with open('config.json', 'r') as f:
                self.config = json.load(f)
        except FileNotFoundError:
            raise ScraperException("Configuration file not found!")
        
        # Initialize from config
        self.user_agents = self.config['scraping']['browser']['user_agents']
        self.max_retries = self.config['scraping']['request']['max_retries']
        self.min_delay = self.config['scraping']['request']['min_delay_seconds']
        self.max_delay = self.config['scraping']['request']['max_delay_seconds']
        
        # Set up data management
        self.data_dir = Path(self.config['scraping']['data_management']['data_directory'])
        self.data_dir.mkdir(exist_ok=True)
        
        # VPN configuration
        self.use_vpn = self.config['scraping']['vpn']['enabled']
        if self.use_vpn:
            self.vpn_config = self.config['scraping']['vpn']
            self.MULLVAD_PATH = self.vpn_config['paths'].get(os.name, '')
            self.MULLVAD_LOCATIONS = []
            for region in self.vpn_config['settings']['preferred_regions']:
                self.MULLVAD_LOCATIONS.extend(self.vpn_config['locations'].get(region, []))
            self.USED_LOCATIONS = deque(maxlen=self.vpn_config['settings']['max_used_locations'])
            self._init_vpn()
        
        # Proxy configuration
        self.use_proxy = self.config['scraping']['proxy']['enabled']
        if self.use_proxy:
            self.proxy_config = self.config['scraping']['proxy']
        
        # Performance settings
        self.performance_config = self.config['performance']['limits']
        
        # Error handling settings
        self.error_config = self.config['scraping']['error_handling']
        self.consecutive_errors = 0

    def _init_vpn(self):
        """Initialize VPN connection."""
        try:
            if not os.path.exists(self.MULLVAD_PATH):
                self.logger.warning("VPN executable not found. VPN functionality will be disabled.")
                self.use_vpn = False
                return

            # Check VPN status with timeout
            timeout = self.vpn_config['settings']['connection_timeout']
            result = subprocess.run([self.MULLVAD_PATH, "status"], 
                                 capture_output=True, text=True, timeout=timeout)
            
            if "Disconnected" in result.stdout:
                self.logger.info("Connecting to VPN...")
                for attempt in range(self.vpn_config['settings']['connection_retry_attempts']):
                    try:
                        subprocess.run([self.MULLVAD_PATH, "connect"], 
                                    timeout=timeout, check=True)
                        time.sleep(self.vpn_config['settings']['connection_retry_delay'])
                        break
                    except subprocess.TimeoutExpired:
                        self.logger.warning(f"VPN connection attempt {attempt + 1} timed out")
                    except subprocess.CalledProcessError as e:
                        self.logger.error(f"VPN connection attempt {attempt + 1} failed: {str(e)}")
                        
            self.logger.info("VPN initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize VPN: {str(e)}")
            self.use_vpn = False

    def _rotate_vpn(self):
        """Rotate VPN connection to a new location."""
        if not self.use_vpn:
            return

        try:
            # Get a new location that hasn't been used recently
            available_locations = [loc for loc in self.MULLVAD_LOCATIONS if loc not in self.USED_LOCATIONS]
            if not available_locations:
                available_locations = self.MULLVAD_LOCATIONS
            
            new_location = random.choice(available_locations)
            self.USED_LOCATIONS.append(new_location)
            
            # Disconnect current connection
            subprocess.run([self.MULLVAD_PATH, "disconnect"])
            time.sleep(2)
            
            # Connect to new location
            subprocess.run([self.MULLVAD_PATH, "relay", "set", "location", new_location])
            time.sleep(1)
            subprocess.run([self.MULLVAD_PATH, "connect"])
            time.sleep(5)  # Wait for connection
            
            self.logger.info(f"Rotated VPN to location: {new_location}")
            
        except Exception as e:
            self.logger.error(f"Failed to rotate VPN: {str(e)}")

    def __del__(self):
        """Clean up resources when the object is destroyed."""
        if not self._cleanup_in_progress:
            self.cleanup()

    def cleanup(self):
        """Clean up resources safely."""
        self._cleanup_in_progress = True
        try:
            if hasattr(self, 'driver') and self.driver:
                try:
                    self.driver.close()
                    time.sleep(0.5)  # Brief pause to allow cleanup
                    self.driver.quit()
                except Exception as e:
                    self.logger.debug(f"Driver cleanup error (safe to ignore): {str(e)}")
                finally:
                    self.driver = None
                    
            # Disconnect VPN if it was enabled
            if self.use_vpn:
                try:
                    subprocess.run([self.MULLVAD_PATH, "disconnect"])
                except Exception as e:
                    self.logger.debug(f"VPN cleanup error: {str(e)}")
                    
        except Exception as e:
            self.logger.debug(f"Final cleanup error (safe to ignore): {str(e)}")
        finally:
            self._cleanup_in_progress = False

    def _get_random_delay(self) -> float:
        """Get a random delay between requests."""
        return random.uniform(self.min_delay, self.max_delay)

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with random user agent."""
        return {"User-Agent": random.choice(self.user_agents)}

    def _get_chrome_driver(self):
        """Get configured Chrome driver."""
        try:
            if self.driver:
                return self.driver
            
            # Configure Chrome options from config
            chrome_options = uc.ChromeOptions()
            browser_options = self.config['scraping']['browser']['options']
            
            # Add arguments from config
            if browser_options['headless']:
                chrome_options.add_argument('--headless=new')
            if browser_options['disable_gpu']:
                chrome_options.add_argument('--disable-gpu')
            if browser_options['no_sandbox']:
                chrome_options.add_argument('--no-sandbox')
            if browser_options['disable_dev_shm']:
                chrome_options.add_argument('--disable-dev-shm-usage')
            
            # Add additional stealth arguments
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_argument('--disable-web-security')
            chrome_options.add_argument('--allow-running-insecure-content')
            chrome_options.add_argument('--disable-features=IsolateOrigins,site-per-process')
            chrome_options.add_argument('--ignore-certificate-errors')
            chrome_options.add_argument('--ignore-ssl-errors')
            chrome_options.add_experimental_option('excludeSwitches', ['enable-logging', 'enable-automation'])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            window_size = browser_options['window_size']
            chrome_options.add_argument(f'--window-size={window_size["width"]},{window_size["height"]}')
            chrome_options.add_argument(f'--log-level={browser_options["log_level"]}')
            
            # Get Chrome path for current OS
            chrome_paths = self.config['scraping']['browser']['chrome_paths'].get(os.name, [])
            for path in chrome_paths:
                expanded_path = os.path.expandvars(path)
                if os.path.exists(expanded_path):
                    chrome_options.binary_location = expanded_path
                    break
            else:
                raise ScraperException("Chrome browser not found. Please install Chrome.")
            
            # Create driver with configured timeouts
            driver = uc.Chrome(
                options=chrome_options,
                headless=browser_options['headless'],
                use_subprocess=True
            )
            
            # Set timeouts from config
            driver.set_page_load_timeout(self.performance_config['page_load_timeout'])
            driver.set_script_timeout(self.performance_config['script_timeout'])
            
            # Execute stealth JavaScript
            driver.execute_cdp_cmd('Network.setUserAgentOverride', {
                "userAgent": random.choice(self.user_agents)
            })
            driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                "source": """
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                """
            })
            
            return driver
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Chrome driver: {str(e)}")
            raise ScraperException(f"Failed to initialize Chrome driver: {str(e)}")

    def _wait_for_market_listings(self, driver, timeout=30):
        """Wait for market listings with better error handling and retry logic."""
        self.analysis_logger.info(f"Waiting up to {timeout} seconds for market listings...")
        
        try:
            # First wait for the main container
            WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.ID, "searchResultsRows"))
            )
            
            # Then wait for actual listings
            WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.market_listing_row_link"))
            )
            
            # Additional check for empty results
            time.sleep(2)  # Brief pause to ensure content is loaded
            listings = driver.find_elements(By.CSS_SELECTOR, "div.market_listing_row_link")
            if not listings:
                raise TimeoutException("No market listings found")
                
            return True
            
        except TimeoutException as e:
            # Check for specific error messages
            try:
                error_elem = driver.find_element(By.CLASS_NAME, "market_listing_table_message")
                if error_elem:
                    error_text = error_elem.text.strip()
                    self.analysis_logger.error(f"Market error message: {error_text}")
                    return False
            except:
                pass
                
            self.analysis_logger.error(f"Timeout waiting for market listings: {str(e)}")
            return False

    def scrape_one_page(self, weapon: str, add_ons: List[str], retries: int = 0) -> Optional[bs4.BeautifulSoup]:
        """Scrape a single page with retry logic."""
        page = self.base_url + self.items_dict[weapon] + ''.join([str(add_on) for add_on in add_ons])
        self.logger.debug(f"Scraping page: {page}")
        
        try:
            headers = self._get_headers()
            response = self.session.get(page, headers=headers)
            
            if response.status_code == 429:
                if retries >= self.max_retries:
                    raise ScraperException("Maximum retries reached. Aborting.")
                
                wait = random.uniform(10, 20) * (2 ** retries)
                self.logger.warning(f"Rate limited! Sleeping {wait} seconds before retry... (Retry {retries + 1})")
                time.sleep(wait)
                return self.scrape_one_page(weapon, add_ons, retries + 1)
            
            response.raise_for_status()
            return bs4.BeautifulSoup(response.text, "html.parser")
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Request failed: {str(e)}")
            raise ScraperException(f"Failed to scrape page: {str(e)}")

    def get_last_page(self, weapon: str) -> int:
        """Get the last page number for a weapon category."""
        page = self.base_url + self.items_dict[weapon] + "#p1_price_asc"
        self.logger.debug(f"Loading first page with Selenium: {page}")
        
        driver = None
        try:
            driver = self._get_chrome_driver()
            
            # Add retry logic for page load
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    driver.get(page)
                    break
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise
                    self.logger.warning(f"Page load failed, attempt {attempt + 1} of {max_retries}")
                    time.sleep(2 ** attempt)  # Exponential backoff
            
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CLASS_NAME, 'market_paging_pagelink'))
                )
                html = driver.page_source
                soup = bs4.BeautifulSoup(html, "html.parser")
                pagination = soup.find_all('span', class_='market_paging_pagelink')
                
                if pagination:
                    return int(pagination[-1].text)
                return 1
                
            except TimeoutException:
                self.logger.warning("Timeout waiting for pagination elements")
                return 1
                
        except Exception as e:
            self.logger.error(f"Selenium error: {str(e)}")
            raise ScraperException(f"Failed to get last page: {str(e)}")
            
        finally:
            if driver and driver != self.driver:  # Only quit if it's not the shared driver
                try:
                    driver.quit()
                except Exception:
                    pass

    def scrape_all_pages(self, weapon: str) -> Generator[bs4.BeautifulSoup, None, None]:
        """Generator to scrape all pages for a weapon."""
        try:
            last_page = self.get_last_page(weapon)
            self.logger.info(f"Found {last_page} pages for {weapon}")
            
            for index in range(1, last_page + 1):
                soup = self.scrape_one_page(weapon, [f"#p{index}_price_asc"])
                if soup:
                    yield soup
                time.sleep(self._get_random_delay())
                
        except Exception as e:
            self.logger.error(f"Error scraping pages: {str(e)}")
            raise ScraperException(f"Failed to scrape all pages: {str(e)}")

    def save_weapon_data(self, weapon: str, data: list):
        """Save weapon data to a JSON file in the data directory."""
        file_path = self.data_dir / f"{weapon}.json"
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=4)
        logger.info(f"Saved data for {weapon} to {file_path}")

    def get_items(self, weapon: str) -> Generator[Dict[str, Any], None, None]:
        """Get all items for a weapon category."""
        self.analysis_logger.info(f"=== Starting analysis for {weapon.upper()} ===")
        self.analysis_logger.info(f"Timestamp: {datetime.datetime.now().isoformat()}")
        self.logger.info(f"Scraping items for {weapon}")
        
        try:
            all_objs = []
            last_update_time = time.time()
            update_interval = 2.0
            
            self.analysis_logger.info("Initializing progress display and panels")
            
            # Create progress display
            progress = Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeRemainingColumn(),
                console=self.console,
                refresh_per_second=2,
                expand=True
            )
            
            # Create panels
            stats_panel = Panel(
                "",
                title="[bold cyan]🔍 Scraping Statistics[/bold cyan]",
                border_style="cyan"
            )
            
            details_panel = Panel(
                "",
                title="[bold yellow]⚙️ Operation Details[/bold yellow]",
                border_style="yellow"
            )

            def update_panels():
                """Update panels with current information"""
                details_text = Text()
                details_text.append(f"\nTarget Weapon: [cyan]{weapon.upper()}[/cyan]\n")
                if self.use_vpn:
                    details_text.append(f"VPN Status: [green]Active[/green]\n")
                details_text.append(f"Retry Count: [yellow]{retry_count}/{max_retries}[/yellow]\n")
                details_panel.renderable = details_text

                if all_objs:
                    stats_text = Text()
                    stats_text.append(f"\n📊 [bold]Analysis Summary[/bold]\n", style="cyan")
                    stats_text.append(f"Total Items Found: [green]{len(all_objs)}[/green]\n")
                    if len(all_objs) > 0:
                        stats_text.append("\n[bold]Latest Items:[/bold]\n")
                        for i, item in enumerate(all_objs[-3:], 1):
                            stats_text.append(f"{i}. {item['name']} - {item['price']}\n", style="dim")
                    stats_panel.renderable = stats_text

                self.console.print()
                self.console.print(details_panel)
                self.console.print(stats_panel)

            # Start progress display
            with progress:
                # Create tasks
                setup_task = progress.add_task("[cyan]Setting up browser...", total=100)
                connect_task = progress.add_task("[magenta]Connecting to Steam Market...", total=100, visible=False)
                items_task = progress.add_task("[green]Processing items...", total=100, visible=False)
                
                retry_count = 0
                max_retries = self.error_config['max_consecutive_errors']
                driver = None
                
                try:
                    # Configure scraper and initialize driver (only once)
                    self.analysis_logger.info("Configuring scraper and constructing URL")
                    progress.update(setup_task, advance=30)
                    
                    # Construct proper Steam Market URL
                    weapon_info = self.items_dict[weapon]
                    weapon_name = weapon_info["name"]
                    weapon_tag = weapon_info["tag"]
                    full_url = (
                        f"{self.base_url}search?"
                        f"q={weapon_name}&"
                        f"category_730_ItemSet%5B%5D=any&"
                        f"category_730_Weapon%5B%5D=tag_weapon_{weapon_tag}&"
                        f"category_730_Quality%5B%5D=any&"
                        f"appid=730&"
                        f"sort_column=price&"
                        f"sort_dir=asc"
                    )
                    
                    self.analysis_logger.info(f"Constructed URL: {full_url}")
                    progress.update(setup_task, advance=20)
                    update_panels()
                    
                    self.analysis_logger.info("Initializing Chrome driver")
                    driver = self._get_chrome_driver()
                    progress.update(setup_task, completed=100)
                    
                    while retry_count < max_retries:
                        try:
                            # Connect to Steam Market
                            progress.update(connect_task, visible=True)
                            driver.get(full_url)
                            time.sleep(5)  # Increased initial wait
                            
                            # Wait for market listings with better handling
                            if not self._wait_for_market_listings(driver):
                                raise ScraperException("Market listings not found")
                            
                            progress.update(connect_task, completed=100)
                            progress.update(items_task, visible=True)
                            
                            # Process items
                            items = driver.find_elements(By.CSS_SELECTOR, "div.market_listing_row_link")
                            if not items:
                                raise ScraperException("No items found")
                            
                            total_items = len(items)
                            progress.update(items_task, total=total_items)
                            
                            for idx, item in enumerate(items, 1):
                                try:
                                    name_elem = item.find_element(By.CSS_SELECTOR, "span.market_listing_item_name")
                                    price_elem = item.find_element(By.CSS_SELECTOR, "span.market_listing_price_with_fee")
                                    
                                    name = name_elem.text.strip()
                                    price = price_elem.text.strip()
                                    
                                    if name and price:
                                        name_text, stat, souv, wear = self._parse_name(name)
                                        price_text = self._parse_price(price)
                                        
                                        obj = {
                                            "name": name_text,
                                            "price": price_text,
                                            "stat": stat,
                                            "souv": souv,
                                            "wear": wear,
                                            "timestamp": datetime.datetime.now().isoformat()
                                        }
                                        all_objs.append(obj)
                                        
                                        # Update progress
                                        progress.update(
                                            items_task,
                                            advance=1,
                                            description=f"[green]Processing items... ({idx}/{total_items})"
                                        )
                                        
                                        # Update panels less frequently
                                        if idx % 10 == 0:
                                            update_panels()
                                except Exception as e:
                                    self.analysis_logger.error(f"Failed to parse item {idx}: {str(e)}")
                                    continue
                            
                            # Final updates
                            progress.update(items_task, completed=total_items)
                            update_panels()
                            
                            if all_objs:
                                break
                                
                        except Exception as e:
                            retry_count += 1
                            if retry_count >= max_retries:
                                raise ScraperException(f"Failed to scrape after {max_retries} attempts")
                            time.sleep(5)
                
                finally:
                    if driver and driver != self.driver:
                        driver.quit()
                
            return all_objs
            
        except Exception as e:
            error_msg = f"Error getting items: {str(e)}"
            self.analysis_logger.error(error_msg)
            self.logger.error(error_msg)
            raise ScraperException(error_msg)

    def _parse_name(self, name: str) -> tuple:
        """Parse item name into components."""
        stat = "StatTrak™" in name
        souv = "Souvenir" in name
        wear_match = re.search(r'\((.*?)\)', name)
        wear = wear_match.group(1) if wear_match else None
        
        # Clean name
        clean_name = name
        if stat:
            clean_name = clean_name.replace("StatTrak™ ", "")
        if souv:
            clean_name = clean_name.replace("Souvenir ", "")
        if wear:
            clean_name = clean_name.replace(f"({wear})", "")
        
        return clean_name.strip(), stat, souv, wear

    def _parse_price(self, price: str) -> str:
        """Parse and clean price string."""
        return price.split('\n')[1].strip() if '\n' in price else price