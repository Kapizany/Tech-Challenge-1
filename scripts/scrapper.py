# scripts/scrapper.py
import asyncio
import logging
import os
import re
import requests
import aiohttp
from bs4 import BeautifulSoup
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)

BASE_URL = "https://books.toscrape.com/"

def extract_book_id(url: str) -> int | None:
    match = re.search(r"_(\d+)/index\.html$", url)
    return int(match.group(1)) if match else None

async def scrape_category_from_book_page_async(session, book_url: str) -> str:
    try:
        async with session.get(book_url) as response:
            response.raise_for_status()
            html = await response.text()
    except aiohttp.ClientError as e:
        logger.error(f"Error fetching book detail URL {book_url}: {e}")
        return "N/A"

    soup = BeautifulSoup(html, "html.parser")
    breadcrumb = soup.find("ul", class_="breadcrumb")
    if breadcrumb:
        items = breadcrumb.find_all("li")
        if len(items) >= 3:
            category_element = items[2].find("a")
            if category_element:
                return category_element.get_text(strip=True)

    return "N/A"

async def scrape_book_page_async(session, url: str) -> list[dict]:
    try:
        async with session.get(url) as response:
            response.raise_for_status()
            html = await response.text()
    except aiohttp.ClientError as e:
        logger.error(f"Error fetching URL {url}: {e}")
        return []

    soup = BeautifulSoup(html, "html.parser")
    articles = soup.find_all("article", class_="product_pod")
    if not articles:
        return []

    rating_map = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}
    books_data = []

    for article in articles:
        title = article.h3.a["title"]
        price_text = article.find("p", class_="price_color").get_text(strip=True)
        price_value = float(price_text[1:])

        rating_word = article.find("p", class_="star-rating")["class"][1]
        rating = rating_map.get(rating_word.lower())

        availability = article.find("p", class_="instock availability").get_text(strip=True)

        image_url_relative = article.find("img")["src"].replace("../..", "")
        image_url = BASE_URL + image_url_relative

        detail_relative_url = (
            article.h3.a["href"]
            .replace("../../../", "")
            .replace("catalogue/", "")
        )
        book_url = BASE_URL + "catalogue/" + detail_relative_url
        book_id = extract_book_id(book_url)

        books_data.append(
            {
                "id": book_id,
                "title": title,
                "price": price_value,
                "rating": rating,
                "availability": availability,
                "book_url": book_url,
                "image_url": image_url,
            }
        )

    return books_data

async def main(urls: list[str]) -> list[dict]:
    async with aiohttp.ClientSession() as session:
        tasks = [asyncio.create_task(scrape_book_page_async(session, url)) for url in urls]
        all_pages_data = await asyncio.gather(*tasks)

    all_books_data = []
    for page_data in all_pages_data:
        all_books_data.extend(page_data)
    return all_books_data

def get_total_pages() -> int:
    response = requests.get(BASE_URL, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    current_page = soup.select_one("ul.pager li.current")
    if not current_page:
        return 1
    text = current_page.get_text(strip=True)
    return int(text.split("of")[-1])

def create_pages_urls() -> list[str]:
    total = get_total_pages()
    return [BASE_URL, *[BASE_URL + f"catalogue/page-{n}.html" for n in range(2, total + 1)]]

async def fill_categories_async(df: pd.DataFrame) -> pd.DataFrame:
    async with aiohttp.ClientSession() as session:
        tasks = [scrape_category_from_book_page_async(session, url) for url in df["book_url"]]
        df["category"] = await asyncio.gather(*tasks)

    return df.drop(columns=["book_url"])

async def scrape_to_dataframe() -> pd.DataFrame:
    all_books = await main(create_pages_urls())
    df = pd.DataFrame(all_books)
    df = await fill_categories_async(df)
    return df

def scrape_and_save_csv(output_path: str = "./data/all_books.csv") -> str:
    """
    Synchronous wrapper (safe to call from background threads).
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    df = asyncio.run(scrape_to_dataframe())
    df.to_csv(output_path, index=False, header=True)
    logger.info(f"Data saved to {output_path}. Total books: {len(df)}")
    return output_path

if __name__ == "__main__":
    scrape_and_save_csv("./data/all_books.csv")
