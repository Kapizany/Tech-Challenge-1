import asyncio
import logging
import re
import requests
import aiohttp
from bs4 import BeautifulSoup
import pandas as pd


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

BASE_URL = "https://books.toscrape.com/"

def extract_book_id(url: str) -> int:
    """
    Extracts book ID from URLs like:
    https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html
    """
    match = re.search(r'_(\d+)/index\.html$', url)
    return int(match.group(1)) if match else None

async def scrape_category_from_book_page_async(session, book_url):
    """
    Fetches a single book's detail page and extracts its category
    from the breadcrumb.
    """
    try:
        async with session.get(book_url) as response:
            response.raise_for_status()
            html = await response.text()
    except aiohttp.ClientError as e:
        logger.error(f"Error fetching book detail URL {book_url}: {e}")
        return "N/A"

    soup = BeautifulSoup(html, "html.parser")

    # Example breadcrumb:
    # Home > Books > Mystery > Book Name
    breadcrumb = soup.find("ul", class_="breadcrumb")
    if breadcrumb:
        items = breadcrumb.find_all("li")
        if len(items) >= 3:  
            # items[2] = category name link
            category_element = items[2].find("a")
            if category_element:
                return category_element.get_text(strip=True)

    return "N/A"

async def scrape_book_page_async(session, url):
    """
    Asynchronously scrapes book details from a given URL of books.toscrape.com.
    Converts rating to number, price to float, and extracts currency symbol.
    """
    try:
        async with session.get(url) as response:
            response.raise_for_status()
            html = await response.text()
    except aiohttp.ClientError as e:
        logger.error(f"Error fetching URL {url}: {e}")
        return []

    soup = BeautifulSoup(html, "html.parser")
    books_data = []

    articles = soup.find_all("article", class_="product_pod")
    if not articles:
        return []

    # Rating word → number map
    rating_map = {
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5
    }


    for article in articles:
        # Title
        title = article.h3.a["title"]

        # Price: extract currency + convert to float
        price_text = article.find("p", class_="price_color").get_text(strip=True)
        price_value = float(price_text[1:])     # removes symbol → float


        # Rating: convert word → number
        rating_word = article.find("p", class_="star-rating")["class"][1]
        rating = rating_map.get(rating_word.lower(), None)

        # Availability
        availability = article.find("p", class_="instock availability").get_text(strip=True)

        # Image
        image_url_relative = article.find("img")["src"].replace('../..', '')
        image_url = BASE_URL + image_url_relative

        # Book detail page URL
        detail_relative_url = (
            article.h3.a["href"]
            .replace("../../../", "")
            .replace("catalogue/", "")
        )
        book_url = BASE_URL + "catalogue/" + detail_relative_url
        book_id = extract_book_id(book_url)

        book_details = {
            "id": book_id,
            "title": title,
            "price": price_value,      
            "rating": rating,          
            "availability": availability,
            "book_url": book_url,
            "image_url": image_url
        }

        books_data.append(book_details)

    return books_data


async def main(urls):
    """
    Asynchronously scrapes book data from a list of URLs.

    Args:
        urls: A list of URLs to scrape.

    Returns:
        A flattened list of dictionaries, where each dictionary contains the
        details of a book.
    """
    all_books_data = []
    async with aiohttp.ClientSession() as session:
        tasks = []
        for url in urls:
            task = asyncio.create_task(scrape_book_page_async(session, url))
            tasks.append(task)

        all_pages_data = await asyncio.gather(*tasks)

    # Flatten the list of lists into a single list of book dictionaries
    for page_data in all_pages_data:
        all_books_data.extend(page_data)

    return all_books_data



def get_total_pages():
    response = requests.get(BASE_URL)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    current_page = soup.select_one("ul.pager li.current")
    
    if not current_page:
        return 1
    
    text = current_page.get_text(strip=True)
    total_pages = int(text.split("of")[-1])
    
    return total_pages

def creat_pages_urls():
    return [BASE_URL, *[BASE_URL + f'catalogue/page-{page_num}.html' for page_num in range(2, get_total_pages() + 1)]]

    
async def fill_categories_async(df):
    async with aiohttp.ClientSession() as session:
        
        tasks = []
        for url in df["book_url"]:
            tasks.append(scrape_category_from_book_page_async(session, url))

        # Run all requests at the same time
        categories = await asyncio.gather(*tasks)

    # Assign the results back into the DataFrame
    df["category"] = categories
    
    return df.drop(columns=["book_url"])

if __name__ == '__main__':  

    # Run the main asynchronous function
    all_books_data_async = asyncio.run(main(creat_pages_urls()))

    logger.info(f"Finished asynchronous scraping. Collected data for {len(all_books_data_async)} books.")
    logger.info(all_books_data_async[0])

    df_books_async = pd.DataFrame(all_books_data_async)
    logger.info(f"Collecting category data for {len(all_books_data_async)} books.")
    df_updated = asyncio.run(fill_categories_async(df_books_async))

    # Save the DataFrame to a single CSV file
    df_updated.to_csv('./data/all_books.csv', index=False, header=True)

    logger.info(f"Data saved to all_books.csv. Total books: {len(df_updated)}")