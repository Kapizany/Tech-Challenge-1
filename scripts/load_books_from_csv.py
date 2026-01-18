import csv
import logging
from typing import List

from api.models import Book

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)


def load_books(csv_path: str) -> List[Book]:
    books = []
    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            books.append(Book(**row))
    logger.info(f"Books loaded from {csv_path}")
    return books