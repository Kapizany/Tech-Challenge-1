# Books API & Scraper

This project provides:

* A **FastAPI REST API** to explore a books dataset
* A **scraper / data loader script** to populate the dataset from a CSV file

---

## Project Structure

```
.
├── api/
│   ├── __init__.py
│   ├── api.py          # FastAPI application
│   ├── auth.py         # API key authentication
│   └── models.py       # Pydantic models
│
├── data/
│   └── all_books.csv   # Source dataset
│
├── scripts/
│   ├── __init__.py
│   └── scrapper.py     # Scraper / data loader script
│
├── requirements.txt
├── .gitignore
└── README.md
```

---

## Requirements

* Python **3.10+**
* `pip`
* (Recommended) virtual environment

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/Kapizany/Tech-Challenge-1.git
cd Tech-Challenge-1/
```

---

### 2. Create and activate a virtual environment (recommended)

```bash
python3 -m venv venv
source venv/bin/activate
```

On Windows (PowerShell):

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
```

---

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

---

## Running the API

From the **project root**, start the FastAPI development server:

```bash
uvicorn api.api:app --reload
```

* API base URL:
  `http://127.0.0.1:8000`

* Interactive documentation (Swagger UI):
  `http://127.0.0.1:8000/docs` 

    __All endpoints, parameters, request/response schemas, and authentication requirements are fully documented in this interface.__

* Alternative OpenAPI schema viewer:
  `http://127.0.0.1:8000/redoc`

> **Important:**
> Always run `uvicorn` from the project root so Python can correctly resolve the `api` package.

---

## Authentication

Most endpoints require an API key.

* Header name: `X-API-Key`
* Value: defined in `api/auth.py` (`mysecretkey`)

You can authorize directly in `/docs` using the **Authorize** button.

---

## Running the Scraper / Loader Script

The scraper script can be run independently from the API.

From the **project root**:

```bash
python3 scripts/scrapper.py
```

This script:

* Reads data from `data/all_books.csv`
* Processes / loads books according to its internal logic

> The scraper is intentionally isolated and **does not start the API**.

---


## Common Issues

### `ModuleNotFoundError: No module named 'api'`

Make sure:

* You are in the **project root**
* You run:

  ```bash
  uvicorn api.api:app --reload
  ```

  and **not** `python api/api.py`

---

