import requests
import bs4
import logging
import time
import random
import pprint
import json
import re

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

    def scrape_one_page(self, weapon, add_ons: list):
        page = self.base_url + self.items_dict[weapon] + ''.join([str(add_on) for add_on in add_ons])
        logger.debug(f"Scraping page: {page}")
        
        headers = {"User-Agent": random.choice(self.user_agents)}  # Rotate user agents
        response = self.session.get(page, headers=headers)  # Use session
        
        if response.status_code == 429:
            wait = random.uniform(10, 20)
            logger.warning(f"Rate limited! Sleeping {wait} before retry...")
            time.sleep(wait)  # Randomized backoff
            return self.scrape_one_page(weapon, add_ons)  # Retry after waiting

        soup = bs4.BeautifulSoup(response.text, "html.parser")
        return soup

    def scrape_all_pages(self, weapon):
        index = 0
        while True:
            index += 1
            page = f"#p{index}_price_asc"
            soup = self.scrape_one_page(weapon, [page])
            
            test = soup.find_all('span', class_='market_listing_item_name')
            if len(test) == 0:
                raise StopIteration
                
            yield soup

    def get_items(self, weapon):
        logger.info(f"Scraping items for {weapon}")
        all_objs = []
        for page in self.scrape_all_pages(weapon):
            page_objs = []
            names = page.find_all('span', class_='market_listing_item_name')
            prices = page.find_all('span', class_='normal_price')
            
            for name, price in zip(names, prices):
                
                name, stat, souv, wear = self.clean_name(name)
                price = self.clean_price(price)
                
                obj = {"name":name, "price": price, "stat": stat, "souv": souv, "wear": wear}

                page_objs.append(obj)
                
            pprint.pprint(page_objs)
            time.sleep(random.uniform(2, 5))  # Add delay to prevent detection
            all_objs.extend(page_objs)
            
            with open("items.json", "w") as f:
                #append to file
                json.dump(all_objs, f, indent=4)
            
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