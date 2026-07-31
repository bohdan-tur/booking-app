# Booking API

[![CI](https://github.com/bohdan-tur/booking-app/actions/workflows/ci.yaml/badge.svg)](https://github.com/bohdan-tur/booking-app/actions/workflows/ci.yaml)
[![Python 3.13](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.139-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Tests](https://img.shields.io/badge/tests-139%20passed-brightgreen)](#testing)
[![Coverage](https://img.shields.io/badge/coverage-78%25-green)](#testing)

An asynchronous hotel booking REST API built with FastAPI, PostgreSQL, Redis,
and Celery. The project focuses on the backend problems that matter in a real
booking system: concurrent inventory updates, explicit booking lifecycle,
secure token rotation, role-based authorization, background notifications, and
reproducible infrastructure.

## Why this project is more than CRUD

- **Concurrency-safe booking:** availability-changing operations lock the room
  row with PostgreSQL `SELECT ... FOR UPDATE`, check overlapping active
  bookings, and commit the change once.
- **Explicit lifecycle:** bookings transition through `ACTIVE`, `CANCELLED`,
  and `COMPLETED`; cancellation preserves booking history instead of deleting
  the row.
- **Inventory model:** `Room.total_units` represents the number of equivalent
  rooms of one type. Overlapping bookings may coexist up to that capacity.
- **UTC date policy:** booking input must contain a timezone, is normalized to
  UTC, cannot start in the past, and must satisfy `start_time < end_time`.
- **Hardened authentication:** short-lived access tokens, rotating refresh
  tokens stored only as SHA-256 hashes, session revocation, active-user checks,
  password invalidation, and Redis-backed rate limiting.
- **Role-based access control:** separate permissions for `user`, `manager`,
  and `admin`, including negative authorization tests.
- **Background processing:** Celery sends booking emails, completes finished
  bookings, sends reminders, and generates daily statistics. Temporary SMTP
  failures use exponential backoff with jitter.
- **Database-level integrity:** Alembic migrations and PostgreSQL constraints
  protect booking periods, room price, capacity, and inventory.
- **Automated verification:** CI runs Ruff, dependency auditing, the complete
  migration lifecycle, tests, Compose validation, and Docker image builds.

## Architecture

```text
                        +-------------------+
Client / Swagger UI --->| FastAPI API       |
                        | async SQLAlchemy  |
                        +---------+---------+
                                  |
                     +------------+------------+
                     |                         |
                     v                         v
              +-------------+           +-------------+
              | PostgreSQL  |           | Redis       |
              | data/locks  |           | rate limits |
              +-------------+           | Celery      |
                                        +------^------+
                                               |
                                +--------------+--------------+
                                | Celery worker + beat         |
                                | email and scheduled tasks    |
                                +-----------------------------+
```

The API uses async SQLAlchemy sessions. Celery workers create their own async
database sessions, while Redis acts as the task broker/result backend and
stores short-lived rate-limit counters.

### Booking transaction

```text
BEGIN
  -> lock the relevant room row
  -> count overlapping ACTIVE bookings
  -> validate total_units
  -> create, update, or cancel the booking
COMMIT
```

For an update, the overlap query excludes the booking being changed. Only
`ACTIVE` bookings block availability; cancelled bookings immediately release
inventory. An inactive room cannot receive new bookings, but its historical
bookings remain intact.

## Tech stack

| Area | Technologies |
|---|---|
| API | Python 3.13, FastAPI, Uvicorn, Pydantic v2 |
| Database | PostgreSQL 15, SQLAlchemy 2 async, asyncpg, Alembic |
| Authentication | JWT, Argon2, rotating refresh-token sessions |
| Background jobs | Celery, Redis, Celery Beat, Flower |
| Testing | Pytest, pytest-asyncio, HTTPX, pytest-cov |
| Quality and CI | Ruff, pip-audit, GitHub Actions, Docker Compose |

## Project structure

```text
booking-app/
|-- app/
|   |-- api/
|   |   |-- dependencies.py       # DB, authentication, RBAC, pagination
|   |   `-- routers/              # Auth, users, rooms, bookings, system
|   |-- core/                     # Settings, JWT/password security, logging
|   |-- db/                       # Async engine/session and optional seed
|   |-- models/                   # SQLAlchemy ORM models
|   |-- schemas/                  # Pydantic request/response contracts
|   |-- services/                 # Booking, refresh-token, email, rate-limit logic
|   |-- workers/                  # Celery application and tasks
|   |-- alembic/                  # Migration environment and revisions
|   `-- main.py                   # FastAPI application
|-- tests/                        # API, security, concurrency, and worker tests
|-- .github/workflows/ci.yaml     # CI pipeline
|-- docker-compose.yaml           # Local application and test infrastructure
|-- Dockerfile                    # Runtime, test, and production stages
|-- requirements.txt
|-- requirements-dev.txt
`-- alembic.ini
```

## Quick start with Docker

### Prerequisites

- Docker Engine with Docker Compose
- Git

### 1. Clone and configure

```bash
git clone https://github.com/bohdan-tur/booking-app.git
cd booking-app
cp .env.example .env
```

Replace the placeholder database password, token secrets, seed passwords, SMTP
credentials, and Flower credentials in `.env`.

Generate two different secrets, each at least 32 bytes long:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

### 2. Start the application

```bash
docker compose up -d --build
docker compose ps
```

Compose waits for PostgreSQL, applies `alembic upgrade head`, and then starts
the API, Redis, Celery worker, and Celery Beat.

| Service | Address |
|---|---|
| Swagger UI | <http://localhost:8001/docs> |
| ReDoc | <http://localhost:8001/redoc> |
| API readiness | <http://localhost:8001/system/ready> |
| PostgreSQL | `localhost:5436` |
| Redis | `localhost:6381` |

Flower is optional and protected with basic authentication:

```bash
docker compose --profile monitoring up -d flower
```

It is then available at <http://localhost:5555>.

### 3. Seed demo users (optional)

Seeding is allowed only in `development` and only when explicitly enabled:

```env
ENVIRONMENT=development
SEED_DEFAULT_USERS=true
```

The seed is idempotent and creates `admin`, `manager`, and `user` accounts with
the passwords configured in `.env`. Set `SEED_DEFAULT_USERS=false` after the
first startup if you no longer need startup seeding. Production configuration
rejects enabled demo-user seeding.

### Stop the stack

```bash
docker compose down
```

Add `-v` only when you intentionally want to remove PostgreSQL and Redis
volumes as well.

## Configuration

The complete template is available in [`.env.example`](.env.example).

| Variable | Purpose | Typical development value |
|---|---|---|
| `ENVIRONMENT` | `development`, `test`, or `production` | `development` |
| `DEBUG` | FastAPI debug mode | `false` |
| `DATABASE_URL` | Async application database DSN | PostgreSQL URL for `db` |
| `TEST_DATABASE_URL` | Isolated test database DSN | PostgreSQL URL for `db_test` |
| `REDIS_URL` | Celery and rate-limit storage | `redis://redis:6379/0` |
| `SECRET_KEY` | Access-token signing key | unique 32+ byte secret |
| `REFRESH_SECRET_KEY` | Refresh-token signing key | different 32+ byte secret |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access-token lifetime | `15` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Refresh-token lifetime | `7` |
| `SEED_DEFAULT_USERS` | Enable development seed on startup | `false` |
| `SMTP_*`, `EMAIL_FROM` | Email transport and sender | SMTP provider settings |
| `TIMEZONE` | Celery scheduling timezone | `UTC` |
| `FLOWER_BASIC_AUTH` | Flower credentials | `admin:strong-password` |

When `ENVIRONMENT=production`, startup fails if debug or seeding is enabled,
if either signing key is still the development default, if the keys are equal,
or if either key is shorter than 32 bytes.

## API overview

All collection endpoints use stable ascending ID ordering. Paginated endpoints
accept `offset` (default `0`) and `limit` (default `20`, maximum `100`). Empty
collections return `200 []`.

| Method | Endpoint | Access | Purpose |
|---|---|---|---|
| `POST` | `/auth/register` | Public | Register an account |
| `POST` | `/auth/login` | Public | Issue access and refresh tokens |
| `POST` | `/auth/refresh` | Public, refresh token body | Rotate the refresh token and issue a new pair |
| `POST` | `/auth/logout` | Refresh token body | Revoke one refresh session |
| `POST` | `/auth/logout-all` | Authenticated | Revoke every session and invalidate existing access tokens |
| `GET` | `/users/me` | Authenticated | Read the current profile |
| `PATCH` | `/users/me/password` | Authenticated | Change password after checking the current password |
| `GET` | `/users/` | Manager/Admin | List users with pagination |
| `GET` | `/users/{user_id}` | Manager/Admin | Read a user |
| `PATCH` | `/users/{user_id}/role` | Admin | Change a non-admin role |
| `PATCH` | `/users/deactivate/{user_id}` | Admin | Deactivate a non-admin account |
| `PATCH` | `/users/activate/{user_id}` | Admin | Reactivate a non-admin account |
| `DELETE` | `/users/{user_id}` | Admin | Delete a non-admin account |
| `GET` | `/rooms/all` | Public | List active room types with pagination |
| `GET` | `/rooms/available` | Public | List room types available for a period |
| `GET` | `/rooms/{room_id}/available` | Public | Check one room type for a period |
| `GET` | `/rooms/booked` | Manager/Admin | List booked room types for a period |
| `GET` | `/rooms/booked/{room_id}` | Manager/Admin | Check whether a room type is booked |
| `POST` | `/rooms/` | Admin | Create a room type |
| `PATCH` | `/rooms/{room_id}` | Manager/Admin | Update a room type |
| `DELETE` | `/rooms/{room_id}` | Admin | Archive a room type without deleting history |
| `POST` | `/bookings/` | Authenticated | Create a booking |
| `GET` | `/bookings/` | Manager/Admin | List bookings with pagination |
| `GET` | `/bookings/{booking_id}` | Owner/Manager/Admin | Read one booking |
| `PATCH` | `/bookings/{booking_id}` | Manager/Admin | Change an active booking period |
| `DELETE` | `/bookings/{booking_id}` | Owner/Manager/Admin | Cancel without deleting history |
| `GET` | `/system/live` | Public | Liveness probe |
| `GET` | `/system/ready` | Public | PostgreSQL readiness probe |

For room availability endpoints, `start_time` and `end_time` are optional query
parameters. If omitted, the API checks the next 24 hours. When supplied, use
timezone-aware ISO 8601 values.

## API walkthrough

The interactive Swagger UI at <http://localhost:8001/docs> is the quickest way
to explore the API. The examples below use `curl`.

### Register

```bash
curl -X POST http://localhost:8001/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "guest@example.com",
    "username": "guest_user",
    "password": "strong-password"
  }'
```

Emails are normalized to lowercase. Passwords must contain between 8 and 128
characters.

### Log in

The login endpoint follows OAuth2 form encoding. The `username` field accepts
either the username or email address.

```bash
curl -X POST http://localhost:8001/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=guest@example.com&password=strong-password"
```

```json
{
  "access_token": "<jwt>",
  "refresh_token": "<jwt>",
  "token_type": "bearer"
}
```

### Create a booking

```bash
curl -X POST http://localhost:8001/bookings/ \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "room_id": 1,
    "start_time": "2030-08-15T14:00:00Z",
    "end_time": "2030-08-20T11:00:00Z"
  }'
```

```json
{
  "id": 42,
  "room_id": 1,
  "user_id": 5,
  "start_time": "2030-08-15T14:00:00Z",
  "end_time": "2030-08-20T11:00:00Z",
  "status": "ACTIVE"
}
```

If every unit is already occupied during the requested interval, the API
returns `409 Conflict`. Naive datetimes, invalid ranges, and bookings in the
past are rejected.

### Refresh and revoke a session

Refresh rotates the stored token, so the old token cannot be reused:

```bash
curl -X POST http://localhost:8001/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "<refresh_token>"}'
```

Revoke that session with `/auth/logout`, or send an authenticated request to
`/auth/logout-all` to revoke all refresh sessions and invalidate previously
issued access tokens.

## Authentication and abuse protection

JWT payloads contain `sub`, `exp`, `iat`, and `type`. Access and refresh tokens
use separate secrets, and each verifier accepts only the expected token type.
Every authenticated request reloads the user and rejects deactivated accounts
or tokens issued before the user's invalidation timestamp.

Refresh tokens are stored as SHA-256 hashes rather than raw credentials. Token
rotation locks the matching session row, which also prevents two concurrent
refresh requests from successfully reusing the same token.

Redis rate limits login by IP and account, registration by IP, and refresh by
IP. A rejected request returns `429` with the remaining window in the
`Retry-After` header. If Redis is temporarily unavailable, authentication
remains available and the failure is logged without credentials or tokens.

## Background tasks

Celery Beat schedules:

- completion of finished active bookings every hour;
- reminders for bookings starting the next day at 09:00;
- a daily booking report for admins at 23:59.

Booking creation and cancellation also enqueue email notifications. Email is a
secondary feature: if Redis is unavailable after the database transaction has
committed, the API preserves the successful booking response and logs only
non-sensitive task metadata. Transient SMTP and connection errors are retried
up to three times with exponential backoff and jitter; permanent SMTP errors
are not retried indefinitely.

## Testing

The test suite uses a dedicated PostgreSQL container because row locks and
concurrency behavior cannot be validated faithfully with an in-memory database.

```bash
docker compose run --rm tests
```

Run with coverage:

```bash
docker compose run --rm tests \
  pytest --cov=app --cov-report=term-missing
```

Current result:

```text
139 passed
78% total coverage
```

The suite covers authentication and refresh rotation, negative authorization,
pagination and response contracts, booking lifecycle, cancelled-booking
availability, room archival, Celery retry behavior, and real PostgreSQL race
conditions. Concurrency cases include 20 simultaneous booking attempts against
inventory of one and three units, concurrent create/update operations, and two
updates competing for the same availability.

## Database migrations

Migrations run automatically in Compose. For manual migration work inside the
application container:

```bash
docker compose run --rm alembic alembic current
docker compose run --rm alembic alembic upgrade head
```

The CI pipeline verifies `upgrade -> downgrade base -> upgrade`, then checks
that the ORM metadata does not introduce an uncommitted schema migration.

## Quality checks

```bash
ruff check .
ruff format --check .
pip-audit -r requirements.txt
```

GitHub Actions runs these checks together with migrations, tests, Compose
validation, and runtime/test image builds on every pull request to `main`.

## Author

**Bohdan Turevych**

- GitHub: [@bohdan-tur](https://github.com/bohdan-tur)
- LinkedIn: [Bohdan Turevych](https://www.linkedin.com/in/bohdan-turevych)
