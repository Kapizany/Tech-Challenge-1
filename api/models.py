from typing import Dict
from pydantic import BaseModel, Field


class Book(BaseModel):
    id: int
    title: str
    price: float
    rating: int
    availability: str
    category: str
    image_url: str


class HealthResponse(BaseModel):
    status: str = Field(..., examples=["ok"])
    books_loaded: int = Field(..., examples=[1000])

class OverviewStats(BaseModel):
    total_books: int
    average_price: float
    rating_distribution: Dict[int, int]

class CategoryStats(BaseModel):
    count: int
    total_price: float
    average_price: float

