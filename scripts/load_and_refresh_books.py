import csv
import logging
from pathlib import Path
from typing import List
from api.models import Book
from scripts.scrapper import scrape_and_save_csv

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)


def load_books(csv_path: str) -> List[Book]:
    path = Path(csv_path)

    if not path.exists():
        logger.warning(f"Books file not found: {csv_path}")
        return []

    if path.stat().st_size == 0:
        logger.warning(f"Books file is empty: {csv_path}")
        return []

    books: List[Book] = []

    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                books.append(Book(**row))
            except Exception as e:
                logger.error(f"Invalid row skipped: {row} | Error: {e}")

    logger.info(f"Books loaded from {csv_path}. Total: {len(books)}")
    return books

def scrape_job(SCRAPE_STATE: dict, DATA_PATH: str):
    try:
        SCRAPE_STATE["running"] = True
        SCRAPE_STATE["last_error"] = None

        output_path = scrape_and_save_csv(DATA_PATH)
        books = load_books(output_path)
        import api.api as api_module
        api_module.BOOKS = books

        SCRAPE_STATE["last_success_path"] = output_path
    except Exception as e:
        SCRAPE_STATE["last_error"] = str(e)
        logger.info(f"Error scrapping books {str(e)}")
    finally:
        SCRAPE_STATE["running"] = False