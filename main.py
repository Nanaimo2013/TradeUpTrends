from bs4 import BeautifulSoup
from urllib.request import urlopen

url = "https://steamcommunity.com/market/search?q=&category_730_ItemSet%5B%5D=tag_set_baggage&category_730_ProPlayer%5B%5D=any&category_730_StickerCapsule%5B%5D=any&category_730_Tournament%5B%5D=any&category_730_TournamentTeam%5B%5D=any&category_730_Type%5B%5D=any&category_730_Weapon%5B%5D=any&appid=730"
page = urlopen(url)

html = page.read().decode("utf-8")
soup = BeautifulSoup(html, "html.parser")

prices = soup.find_all('span', class_='normal_price')

for price in prices:
    print(price.text.strip())