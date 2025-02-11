import bs4 
import requests
import re
import httpx
from scraper import Scraper
from temp import items_dict

def main():
    #scrape for ak-47 listings
    
    url = "https://steamcommunity.com/market/"
    
    scraper = Scraper(url, items_dict)
    items, prices = scraper.get_items("ak", )

if __name__ == "__main__":
    main()