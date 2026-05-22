# Student Management API

A REST API for managing student records with full CRUD operations and JWT authentication, built with FastAPI and SQLite.

## Run & Operate

- Start: workflow `artifacts/api-server: API Server` runs the FastAPI server
- Interactive docs: visit `/api/docs` (Swagger UI) or `/api/redoc`
- Database: SQLite file at `artifacts/api-server/students.db` (auto-created on startup)

## Stack

- Python 3.12
- FastAPI + Uvicorn
- SQLite (via stdlib `sqlite3`)
- Pydantic v2 for validation
- `python-jose` for JWT signing/verification
- `bcrypt` for password hashing

## Where things live

- `artifacts/api-server/main.py` — FastAPI app, all route handlers
- `artifacts/api-server/database.py` — SQLite connection and schema init
- `artifacts/api-server/models.py` — Pydantic request/response models
- `artifacts/api-server/auth.py` — JWT creation/verification, bcrypt helpers, auth dependency
- `artifacts/api-server/students.db` — SQLite database (auto-created)

## API Endpoints

### Auth (public)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/register` | Create a user account |
| POST | `/api/auth/login` | Receive a JWT bearer token |
| GET | `/api/auth/me` | Get current user profile (requires token) |

### Students (all require `Authorization: Bearer <token>`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/healthz` | Health check |
| POST | `/api/students` | Create a student |
| GET | `/api/students` | List all students (search, grade filter, pagination) |
| GET | `/api/students/{id}` | Get student by ID |
| PUT | `/api/students/{id}` | Update a student (partial updates supported) |
| DELETE | `/api/students/{id}` | Delete a student |
| GET | `/api/students/stats/summary` | Summary stats (total, avg age, by grade) |

## Auth Flow

1. `POST /api/auth/register` with `{"username": "...", "password": "..."}` — create account
2. `POST /api/auth/login` with same credentials — receive `access_token`
3. Pass token in header: `Authorization: Bearer <access_token>` on all student requests

## Student Fields

- `id` — auto-assigned integer
- `name` — string (required)
- `email` — unique string (required)
- `age` — integer 1–120 (required)
- `grade` — string (required)
- `created_at` — ISO timestamp (auto-set)

## Architecture decisions

- SQLite chosen for zero-config persistence; swap to PostgreSQL by changing `DB_PATH` in `database.py`
- Partial updates via `PUT` using `model_dump(exclude_none=True)` — no separate PATCH needed
- `BASE_PATH` env var support for reverse-proxy path prefix (`root_path` in FastAPI)
- `SESSION_SECRET` env var used as JWT signing key (falls back to a default for development)
- Token expiry configurable via `ACCESS_TOKEN_EXPIRE_MINUTES` env var (default: 60 minutes)
- CORS enabled for all origins for easy frontend integration
- `bcrypt` used directly (no passlib wrapper) to avoid bcrypt ≥4.0 compatibility issues

## Gotchas

- `stats/summary` route must be declared before `/{student_id}` in the router to avoid path conflict
- SQLite `students.db` is created relative to `main.py`'s directory on first startup
