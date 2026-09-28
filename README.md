# URL Shortener Service

A high-throughput Django URL shortener with Redis caching, click analytics, and API-based short URL creation. It stores original URLs, generates compact short codes, caches popular redirects in Redis, and tracks click metadata for reporting.

## Features

- Fast URL redirects using Redis cache-aside logic
- PostgreSQL-backed persistence with atomic click updates
- API endpoint to shorten a URL
- Redirect endpoint for visiting shortened links
- Click analytics stored per shortened URL
- Docker support for local development and demo setup

## Tech Stack

- Python 3.12
- Django 6.1+
- PostgreSQL
- Redis
- Django REST Framework
- Docker / Docker Compose

## Project Structure

- `core/` — Django project settings and URL configuration
- `shortener/` — URL shortening app, serializers, views, cache helpers, and models
- `manage.py` — Django management entry point
- `requirements.txt` — Python dependencies
- `docker-compose.yml` — Docker services for app, PostgreSQL, and Redis
- `Dockerfile` — app container build
- `example.env` — environment variable template

## API Endpoints

### Create a short URL

- Method: `POST`
- Endpoint: `/api/shorten/`
- Body:

```json
{
  "url": "https://example.com/very/long/url"
}
```

Example response:

```json
{
  "short_code": "abc123",
  "original_url": "https://example.com/very/long/url",
  "short_url": "http://127.0.0.1:8000/r/abc123"
}
```

### Redirect a short URL

- Method: `GET`
- Endpoint: `/r/<short_code>/`

## Local Development Setup

### Prerequisites

- Python 3.10+
- Redis
- PostgreSQL
- pip

### 1. Clone the repository

```bash
git clone https://github.com/Arbinchaudhary240/django-high-throughput-url-shortener.git
cd django-high-throughput-url-shortener
```

### 2. Create and activate a virtual environment

On macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

On Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Copy the example file and update the values for your local machine:

```bash
copy example.env .env
```

Then update `.env` with your local values, for example:

```env
DJANGO_DEBUG=true
DJANGO_SECRET_KEY=your-secret-key
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost,0.0.0.0

DB_NAME=url_shortener
DB_USER=postgres
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5432
```

### 5. Create the database and run migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

### 6. Start the development server

```bash
python manage.py runserver
```

The app will be available at:

- http://127.0.0.1:8000/

## Docker Setup

This project includes Docker configuration for running the app, PostgreSQL, and Redis together.

### Prerequisites

- Docker
- Docker Compose

### 1. Create the environment file

```bash
copy example.env .env
```

### 2. Build and start containers

```bash
docker compose up --build
```

This starts:

- Django app on `http://localhost:8000`
- PostgreSQL on `localhost:5432`
- Redis on `localhost:6379`

### 3. Run database migrations inside the app container

```bash
docker compose exec web python manage.py migrate
```

### 4. Stop the containers

```bash
docker compose down
```

To remove the PostgreSQL data volume as well:

```bash
docker compose down -v
```

## Notes

- The app uses `DJANGO_ALLOWED_HOSTS` and `DJANGO_SECRET_KEY` for safe local and deployment setup.
- Redis is used as a cache for redirect lookups and improved response time.
- The app is designed for local development and can be extended for production deployment with proper security settings and a production-grade WSGI server.

## Common Commands

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py runserver
python manage.py shell
```

```bash
docker compose up --build
docker compose exec web python manage.py migrate
docker compose down
```
