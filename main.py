import bs4 
import requests
import re
import httpx
from scraper import Scraper
from temp import items_dict
import json

def main():
    #scrape for ak-47 listings
    
    url = "https://steamcommunity.com/market/"
    
    scraper = Scraper(url, items_dict)
    items = scraper.get_items("ak")
    
# def load_items():
#     #load items from file
#     with open("items.json", "r") as f:
#         items = json.load(f)
        
#         print(len(items['ak']))

if __name__ == "__main__":
    main()