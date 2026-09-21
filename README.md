# High-Throughput URL Shortener & Analytics Service

A lightweight, high-performance URL shortening microservice built with Django and Redis. Designed to handle high-volume link redirections using in-memory caching and atomic database operations to mitigate race conditions under heavy concurrent loads.

---

## Architecture & System Flow

The primary bottleneck in redirection services is database read performance under peak traffic. This application addresses that by implementing a **cache-aside pattern** via Redis, ensuring the database is only queried on a cache miss.

## key features

* **In-Memory Caching ($O(1)$ Lookups):** Hot URLs are cached in Redis, allowing redirections to bypass the database entirely and serve responses in milliseconds.
* **B-Tree Database Indexing:** The `short_code` database column uses `db_index=True`, reducing search complexity from $O(N)$ full-table scans to $O(\log N)$ tree lookups on cache misses.
* **Atomic Race Condition Prevention:** Increments click metrics using Django `F()` expressions directly in SQL (`UPDATE url SET clicks = clicks + 1`), avoiding race conditions without database row locking.
* **Non-Blocking Telemetry:** Logs detailed click metadata (IP address, referrers, user agents) into an isolated `ClickAnalytics` table to keep the primary `ShortURL` model compact.
* **Cryptographically Secure Short Codes:** Replaces sequential auto-increment IDs with `secrets.choice` PRNG generation to stop code enumeration and URL harvesting.

## Tech Stack

* **Framework:** Python / Django
* **In-Memory Cache:** Redis
* **Database:** PostgreSQL / SQLite
* **Analytics & Logging:** Django ORM with atomic update strategy

## Local Setup

### Prerequisites
* Python 3.10+
* Redis Server (running locally or via Docker)

1. **Clone the repository**

   ```bash
   git clone https://github.com/Arbinchaudhary240/django-high-throughput-url-shortener.git
   cd django-high-throughput-url-shortener


2. **Create a virtual environment**

    ```bash
    python3 -m venv .vemv
    source env/bin/activate  # On Windows use `.\.venv\Scripts\activate`

3. **Install dependencies**

    ```bash
    pip install -r requirements.txt

4. **Set up the database**

    ```bash
    python manage.py makemigrations
    python manage.py migrate

5. Run the development server

    ```bash
    python manage.py runserver


App will be available at http://127.0.0.1:8000/.