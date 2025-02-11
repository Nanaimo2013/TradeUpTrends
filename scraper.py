import re
import time
import random
import requests
import bs4
import json
import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from typing import List, Dict, Any, Optional, Generator

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class ScraperException(Exception):
    """Custom exception for scraper-related errors."""
    pass

class Scraper:
    def __init__(self, url: str, items_dict: Dict[str, str]):
        self.base_url = url
        self.items_dict = items_dict
        self.session = requests.Session()
        
        # Load configuration
        try:
            with open('config.json', 'r') as f:
                self.config = json.load(f)
        except FileNotFoundError:
            raise ScraperException("Configuration file not found!")
        
        self.user_agents = self.config['scraping']['user_agents']
        self.max_retries = self.config['scraping']['max_retries']
        self.min_delay = self.config['scraping']['min_delay']
        self.max_delay = self.config['scraping']['max_delay']

    def _get_random_delay(self) -> float:
        """Get a random delay between requests."""
        return random.uniform(self.min_delay, self.max_delay)

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with random user agent."""
        return {"User-Agent": random.choice(self.user_agents)}

    def scrape_one_page(self, weapon: str, add_ons: List[str], retries: int = 0) -> Optional[bs4.BeautifulSoup]:
        """Scrape a single page with retry logic."""
        page = self.base_url + self.items_dict[weapon] + ''.join([str(add_on) for add_on in add_ons])
        logger.debug(f"Scraping page: {page}")
        
        try:
            headers = self._get_headers()
            response = self.session.get(page, headers=headers)
            
            if response.status_code == 429:
                if retries >= self.max_retries:
                    raise ScraperException("Maximum retries reached. Aborting.")
                
                wait = random.uniform(10, 20) * (2 ** retries)
                logger.warning(f"Rate limited! Sleeping {wait} seconds before retry... (Retry {retries + 1})")
                time.sleep(wait)
                return self.scrape_one_page(weapon, add_ons, retries + 1)
            
            response.raise_for_status()
            return bs4.BeautifulSoup(response.text, "html.parser")
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {str(e)}")
            raise ScraperException(f"Failed to scrape page: {str(e)}")

    def get_last_page(self, weapon: str) -> int:
        """Get the last page number for a weapon category."""
        page = self.base_url + self.items_dict[weapon] + "#p1_price_asc"
        logger.debug(f"Loading first page with Selenium: {page}")
        
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        
        try:
            driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=options)
            driver.get(page)
            
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
                logger.warning("Timeout waiting for pagination elements")
                return 1
                
        except WebDriverException as e:
            logger.error(f"Selenium error: {str(e)}")
            raise ScraperException(f"Failed to get last page: {str(e)}")
            
        finally:
            if 'driver' in locals():
                driver.quit()

    def scrape_all_pages(self, weapon: str) -> Generator[bs4.BeautifulSoup, None, None]:
        """Generator to scrape all pages for a weapon."""
        try:
            last_page = self.get_last_page(weapon)
            logger.info(f"Found {last_page} pages for {weapon}")
            
            for index in range(1, last_page + 1):
                soup = self.scrape_one_page(weapon, [f"#p{index}_price_asc"])
                if soup:
                    yield soup
                time.sleep(self._get_random_delay())
                
        except Exception as e:
            logger.error(f"Error scraping pages: {str(e)}")
            raise ScraperException(f"Failed to scrape all pages: {str(e)}")

    def get_items(self, weapon: str) -> List[Dict[str, Any]]:
        """Get all items for a weapon category."""
        logger.info(f"Scraping items for {weapon}")
        all_objs = []
        page_index = 0
        item_index = 0
        
        try:
            for page in self.scrape_all_pages(weapon):
                page_index += 1
                page_objs = []
                
                names = page.find_all('span', class_='market_listing_item_name')
                prices = page.find_all('span', class_='normal_price')
                
                for name, price in zip(names, prices):
                    item_index += 1
                    name, stat, souv, wear = self.clean_name(name)
                    price = self.clean_price(price)
                    
                    obj = {
                        "name": name,
                        "price": price,
                        "stat": stat,
                        "souv": souv,
                        "wear": wear,
                        "page": page_index,
                        "item": item_index
                    }
                    
                    page_objs.append(obj)
                    
                logger.debug(f"Scraped {len(page_objs)} items from page {page_index}")
                all_objs.extend(page_objs)
                
                # Save progress
                self._save_items(weapon, all_objs)
                
            return all_objs
            
        except Exception as e:
            logger.error(f"Error getting items: {str(e)}")
            raise ScraperException(f"Failed to get items: {str(e)}")

    def _save_items(self, weapon: str, items: List[Dict[str, Any]]):
        """Save scraped items to file."""
        try:
            with open("items.json", "w") as f:
                json.dump({weapon: items}, f, indent=4)
        except IOError as e:
            logger.error(f"Failed to save items: {str(e)}")

    def clean_name(self, name_element: bs4.element.Tag) -> tuple:
        """Clean and parse item name."""
        name = name_element.text.strip()
        
        stat = self.check_stattrak(name)
        souv = self.check_souvenir(name)
        wear = self.check_wear(name)
        
        if stat:
            name = name.replace("StatTrak™ ", "")
        if souv:
            name = name.replace("Souvenir ", "")
        if wear:
            name = name.replace(f"({wear})", "")
        
        return name.strip(), stat, souv, wear

    def clean_price(self, price_element: bs4.element.Tag) -> str:
        """Clean and parse item price."""
        price = price_element.text.strip()
        return price.split('\n')[1].strip() if '\n' in price else price

    def check_wear(self, name: str) -> Optional[str]:
        """Extract wear value from name."""
        wear = re.search(r'\((.*?)\)', name)
        return wear.group(1) if wear else None

    def check_souvenir(self, name: str) -> bool:
        """Check if item is souvenir."""
        return "Souvenir" in name

    def check_stattrak(self, name: str) -> bool:
        """Check if item is StatTrak."""
        return "StatTrak" in name