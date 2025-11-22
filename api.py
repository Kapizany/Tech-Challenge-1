import csv
import logging
from fastapi.security.api_key import APIKeyHeader
from fastapi import Depends
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional

# API Key Auth
API_KEY = "mysecretkey"
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)

def verify_api_key(api_key: str = Depends(api_key_header)):
    if api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return True

# ------------------------------
# Data Model
# ------------------------------
class Book(BaseModel):
    id: int
    title: str
    price: float
    rating: int
    availability: str
    category: str
    image_url: str

# ------------------------------
# Load Data from CSV
# ------------------------------
def load_books(csv_path: str) -> List[Book]:
    books = []
    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            books.append(Book(**row))
    return books

BOOKS = load_books("all_books.csv")

app = FastAPI()

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# Logging middleware
@app.middleware(middleware_type="http")
async def log_requests(request, call_next):
    logger.info(f"Request: {request.method} {request.url}")
    response = await call_next(request)
    logger.info(f"Response status: {response.status_code}")
    return response


# ------------------------------
# Core Endpoints
# ------------------------------
@app.get("/api/v1/books/", dependencies=[Depends(verify_api_key)])
def list_books():
    return BOOKS


@app.get("/api/v1/books/search/", dependencies=[Depends(verify_api_key)])
def search_books(title: str|None = None, category: str|None = None):
    results = BOOKS
    if title:
        results = [b for b in results if title.lower() in b.title.lower()]
    if category:
        results = [b for b in results if category.lower() == b.category.lower()]
    return results

@app.get("/api/v1/books/{id}/", dependencies=[Depends(verify_api_key)])
def get_book(id: int):
    for book in BOOKS:
        if book.id == id:
            return book
    raise HTTPException(status_code=404, detail="Book not found")

@app.get("/api/v1/categories", dependencies=[Depends(verify_api_key)])
def list_categories():
    categories = sorted({book.category for book in BOOKS})
    return categories

@app.get("/api/v1/health")
def health_check():
    return {"status": "ok", "books_loaded": len(BOOKS)}

# ------------------------------
# Optional Endpoints (Insights)
# ------------------------------
@app.get("/api/v1/stats/overview")
def stats_overview():
    total = len(BOOKS)
    avg_price = sum(b.price for b in BOOKS) / total if total else 0
    rating_dist = {}
    for b in BOOKS:
        rating_dist[b.rating] = rating_dist.get(b.rating, 0) + 1
    return {
        "total_books": total,
        "average_price": avg_price,
        "rating_distribution": rating_dist,
    }

@app.get("/api/v1/stats/categories")
def stats_by_category():
    stats = {}
    for b in BOOKS:
        if b.category not in stats:
            stats[b.category] = {"count": 0, "total_price": 0}
        stats[b.category]["count"] += 1
        stats[b.category]["total_price"] += b.price

    for category in stats.items():
        category["average_price"] = category["total_price"] / category["count"]
    return stats

@app.get("/api/v1/books/top-rated", response_model=List[Book])
def top_rated():
    if not BOOKS:
        return []
    max_rating = max(b.rating for b in BOOKS)
    return [b for b in BOOKS if b.rating == max_rating]

@app.get("/api/v1/books/price-range", response_model=List[Book])
def price_range(min_value: float, max_value: float):
    return [b for b in BOOKS if min_value <= b.price <= max_value]
