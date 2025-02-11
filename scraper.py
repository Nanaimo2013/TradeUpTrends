import re
import time
import random
import requests
import bs4
import json
import logging
import pprint
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class Scraper:
    def __init__(self, url, items_dict):
        self.base_url = url
        self.items_dict = items_dict
        self.session = requests.Session()

        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
            "Mozilla/5.0 (X11; Linux x86_64)"
        ]

    def scrape_one_page(self, weapon, add_ons: list, retries=0):
        page = self.base_url + self.items_dict[weapon] + ''.join([str(add_on) for add_on in add_ons])
        logger.debug(f"Scraping page: {page}")
        
        headers = {"User-Agent": random.choice(self.user_agents)}  # Rotate user agents
        response = self.session.get(page, headers=headers)  # Use session
        
        if response.status_code == 429:
            if retries >= 10:  # Set a maximum number of retries
                logger.error("Maximum retries reached. Aborting.")
                return None
            
            wait = random.uniform(10, 20) * (2 ** retries)  # Exponential backoff
            logger.warning(f"Rate limited! Sleeping {wait} seconds before retry... (Retry {retries + 1})")
            time.sleep(wait)  # Randomized backoff
            return self.scrape_one_page(weapon, add_ons, retries + 1)  # Retry after waiting

        soup = bs4.BeautifulSoup(response.text, "html.parser")
        return soup

    def get_last_page(self, weapon):
        # Use Selenium to load the first page
        page = self.base_url + self.items_dict[weapon] + f"#p{1}_price_asc"
        logger.debug(f"Loading first page with Selenium: {page}")
        
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")  # Run in headless mode
        driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=options)
        driver.get(page)
        
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, 'market_paging_pagelink'))
            )
            html = driver.page_source
            soup = bs4.BeautifulSoup(html, "html.parser")
        finally:
            driver.quit()
            
        pagination = soup.find_all('span', class_='market_paging_pagelink')
        if pagination:
            last_page = pagination[-1].text
            last = int(last_page)
            return last
        
        return 1

    def scrape_all_pages(self, weapon):
        index = 0
        last_page = 2
        while index < last_page:
            index += 1

            if index == 1:
                last_page = self.get_last_page(weapon)
        
            soup = self.scrape_one_page(weapon, [f"#p{index}_price_asc"])
            
            yield soup

    def get_items(self, weapon):
        logger.info(f"Scraping items for {weapon}")
        all_objs = []
        page_index = 0
        item_index = 0
        for page in self.scrape_all_pages(weapon):
            page_index += 1
            page_objs = []
            names = page.find_all('span', class_='market_listing_item_name')
            prices = page.find_all('span', class_='normal_price')
            
            for name, price in zip(names, prices):
                item_index += 1
                name, stat, souv, wear = self.clean_name(name)
                price = self.clean_price(price)
                
                obj = {"name":name, "price": price, "stat": stat, "souv": souv, "wear": wear, "page": page_index, "item": item_index}

                page_objs.append(obj)
                
            pprint.pprint(page_objs)
            #time.sleep(random.uniform(1, 2))  # Add delay to prevent detection
            all_objs.extend(page_objs)
            
            with open("items.json", "w") as f:
                #append to file
                obj = {f"{weapon}": all_objs}
                json.dump(obj, f, indent=4)
            
        return all_objs
    
    def clean_name(self, name):
        name = name.text.strip()
        
        stat = self.check_stattrak(name)
        souv = self.check_souvenir(name)
        wear = self.check_wear(name)
        
        if stat:
            name = name.replace("StatTrak™ ", "")
        
        if souv:
            name = name.replace("Souvenir ", "")
            
        if wear:
            name = name.replace(f"({wear})", "")
        
        name = name.strip()
        
        return name, stat, souv, wear

    def clean_price(self, price):
        price = price.text.strip()
        # Split the price string by newline and select the first non-empty part
        price = price.split('\n')[1].strip() if '\n' in price else price
        return price


    def check_wear(self, name):
        wear = re.search(r'\((.*?)\)', name)
        if wear:
            return wear.group(1)
        return None

    def check_souvenir(self, name):
        if "Souvenir" in name:
            return True
        return False

    def check_stattrak(self, name):
        if "StatTrak" in name:
            return True
        return False