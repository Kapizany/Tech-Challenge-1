from contextlib import asynccontextmanager
import logging
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException,  Query, Path
from typing import Optional, List, Dict

from api.auth import verify_api_key
from api.models import Book, CategoryStats, HealthResponse, OverviewStats
from scripts.load_and_refresh_books import load_books, scrape_job


DATA_PATH = "./data/all_books.csv"
SCRAPE_STATE = {"running": False, "last_success_path": None, "last_error": None}
BOOKS: List[Book] = []

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ---- Startup ----
    logger.info("Starting application...")
    global BOOKS
    BOOKS = load_books(DATA_PATH)
    logger.info(f"Loaded {len(BOOKS)} books at startup")

    yield

    # ---- Shutdown ----
    logger.info("Shutting down application...")

app = FastAPI(
    title="Books API",
    version="0.0.1",
    lifespan=lifespan,
)

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
    global BOOKS
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
    global BOOKS
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
    global BOOKS
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
    global BOOKS
    return sorted({book.category for book in BOOKS})


@app.get(
    "/api/v1/health",
    response_model=HealthResponse,
    tags=["Health"],
    summary="Health check",
)
def health_check():
    global BOOKS
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
    global BOOKS
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
    global BOOKS
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
    global BOOKS
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
    global BOOKS
    if min_value > max_value:
        raise HTTPException(status_code=422, detail="min_value must be <= max_value")
    return [b for b in BOOKS if min_value <= b.price <= max_value]




# ------------------------------
# Scrapping Endpoints
# ------------------------------


@app.post(
    "/api/v1/admin/scrape-and-reload",
    tags=["Admin"],
    summary="Scrape books and reload dataset",
    dependencies=[Depends(verify_api_key)],
    status_code=202,
)
def scrape_and_reload(background_tasks: BackgroundTasks):
    if SCRAPE_STATE["running"]:
        raise HTTPException(status_code=409, detail="Scrape already running")

    background_tasks.add_task(scrape_job,  SCRAPE_STATE, DATA_PATH)
    return {"status": "scheduled"}

@app.get(
    "/api/v1/admin/scrape-status",
    tags=["Admin"],
    summary="Get scraper job status",
    dependencies=[Depends(verify_api_key)],
)
def scrape_status():
    return SCRAPE_STATE