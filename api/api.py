import logging
from fastapi import Depends, FastAPI, HTTPException,  Query, Path
from typing import Optional, List, Dict

from api.auth import verify_api_key
from api.models import Book, CategoryStats, HealthResponse, OverviewStats
from scripts.load_books_from_csv import load_books


BOOKS = load_books("./data/all_books.csv")

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

@app.get(
    "/api/v1/books/",
    response_model=List[Book],
    tags=["Books"],
    summary="List all books",
    description="Returns the full list of books loaded in memory.",
    dependencies=[Depends(verify_api_key)],
)
def list_books():
    return BOOKS


@app.get(
    "/api/v1/books/search/",
    response_model=List[Book],
    tags=["Books"],
    summary="Search books by title and/or category",
    description=(
        "Filters are optional and can be combined. "
        "If both are provided, results must match both."
    ),
    dependencies=[Depends(verify_api_key)],
)
def search_books(
    title: Optional[str] = Query(
        default=None,
        description="Case-insensitive substring match on the book title.",
        examples=["harry", "python"],
        min_length=1,
    ),
    category: Optional[str] = Query(
        default=None,
        description="Case-insensitive exact match on category.",
        examples=["Travel", "Fiction"],
        min_length=1,
    ),
):
    return [
        b for b in BOOKS
        if (title is None or title.lower() in b.title.lower())
        and (category is None or category.lower() == b.category.lower())
    ]


@app.get(
    "/api/v1/books/{id}/",
    response_model=Book,
    tags=["Books"],
    summary="Get a book by id",
    responses={
        404: {"description": "Book not found"},
        401: {"description": "Unauthorized"},
    },
    dependencies=[Depends(verify_api_key)],
)
def get_book(
    id: int = Path(..., description="Book identifier.", examples=[1], ge=1),
):
    for book in BOOKS:
        if book.id == id:
            return book
    raise HTTPException(status_code=404, detail="Book not found")


@app.get(
    "/api/v1/categories",
    response_model=List[str],
    tags=["Categories"],
    summary="List available categories",
    description="Returns distinct categories found across all books.",
    dependencies=[Depends(verify_api_key)],
)
def list_categories():
    return sorted({book.category for book in BOOKS})


@app.get(
    "/api/v1/health",
    response_model=HealthResponse,
    tags=["Health"],
    summary="Health check",
)
def health_check():
    return {"status": "ok", "books_loaded": len(BOOKS)}


# ------------------------------
# Optional Endpoints (Insights)
# ------------------------------

@app.get(
    "/api/v1/stats/overview",
    response_model=OverviewStats,
    tags=["Stats"],
    summary="Overview stats",
    description="Returns high-level stats: total books, average price, and rating distribution.",
)
def stats_overview():
    total = len(BOOKS)
    avg_price = sum(b.price for b in BOOKS) / total if total else 0.0
    rating_dist: Dict[int, int] = {}
    for b in BOOKS:
        rating_dist[b.rating] = rating_dist.get(b.rating, 0) + 1
    return {
        "total_books": total,
        "average_price": avg_price,
        "rating_distribution": rating_dist,
    }


@app.get(
    "/api/v1/stats/categories",
    response_model=Dict[str, CategoryStats],
    tags=["Stats"],
    summary="Stats grouped by category",
)
def stats_by_category():
    stats: Dict[str, Dict[str, float]] = {}
    for b in BOOKS:
        if b.category not in stats:
            stats[b.category] = {"count": 0, "total_price": 0.0}
        stats[b.category]["count"] += 1
        stats[b.category]["total_price"] += b.price

    # Fix your original bug: you used stats.items() incorrectly.
    out: Dict[str, CategoryStats] = {}
    for cat, v in stats.items():
        out[cat] = CategoryStats(
            count=int(v["count"]),
            total_price=float(v["total_price"]),
            average_price=float(v["total_price"]) / int(v["count"]) if v["count"] else 0.0,
        )
    return out


@app.get(
    "/api/v1/books/top-rated",
    response_model=List[Book],
    tags=["Books"],
    summary="List top-rated books",
    description="Returns all books with the maximum rating found in the dataset.",
)
def top_rated():
    if not BOOKS:
        return []
    max_rating = max(b.rating for b in BOOKS)
    return [b for b in BOOKS if b.rating == max_rating]


@app.get(
    "/api/v1/books/price-range",
    response_model=List[Book],
    tags=["Books"],
    summary="Filter books by price range",
    description="Returns books where price is between min_value and max_value (inclusive).",
)
def price_range(
    min_value: float = Query(..., description="Minimum price (inclusive).", examples=[10.0], ge=0),
    max_value: float = Query(..., description="Maximum price (inclusive).", examples=[50.0], ge=0),
):
    if min_value > max_value:
        raise HTTPException(status_code=422, detail="min_value must be <= max_value")
    return [b for b in BOOKS if min_value <= b.price <= max_value]
