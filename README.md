# Booking API

[![CI](https://github.com/bohdan-tur/booking-app/actions/workflows/ci.yaml/badge.svg)](https://github.com/bohdan-tur/booking-app/actions/workflows/ci.yaml)
[![Python 3.13](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.139-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Tests](https://img.shields.io/badge/tests-139%20passed-brightgreen)](#testing-and-quality)
[![Coverage](https://img.shields.io/badge/coverage-78%25-green)](#testing-and-quality)

An asynchronous hotel-booking REST API built with FastAPI, PostgreSQL, Redis,
and Celery. The project addresses the backend problems behind a booking system:
concurrent inventory updates, an explicit booking lifecycle, secure session
rotation, role-based authorization, background notifications, and reproducible
infrastructure.

## Highlights

- Concurrency-safe availability enforced with PostgreSQL row locks.
- Capacity-aware inventory for multiple equivalent units of one room type.
- Explicit `ACTIVE`, `CANCELLED`, and `COMPLETED` booking states.
- Short-lived access tokens and rotating, hashed refresh-token sessions.
- Role-based permissions for users, managers, and administrators.
- Celery email notifications, reminders, booking completion, and reports.
- Database constraints and Alembic migrations for schema integrity.
- PostgreSQL-backed concurrency tests and a comprehensive CI pipeline.

## Booking integrity

### Concurrency-safe transaction

```text
BEGIN
  -> lock the relevant room row with SELECT ... FOR UPDATE
  -> count overlapping ACTIVE bookings
  -> validate total_units capacity
  -> create, update, or cancel the booking
COMMIT
```

An update excludes the booking being changed from its overlap query. Only
`ACTIVE` bookings consume inventory; cancellation releases capacity without
deleting history. Inactive rooms reject new bookings while keeping their
existing records.

### Time and lifecycle rules

- Input datetimes must include a timezone and are normalized to UTC.
- A booking cannot start in the past.
- Every period must satisfy `start_time < end_time`.
- Cancellation and automatic completion preserve historical records.
- `Room.total_units` controls how many overlapping active bookings may coexist.

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

The API uses async SQLAlchemy sessions. Celery tasks create their own async
database sessions. Redis stores task-queue data and short-lived rate-limit
counters.

## Tech stack

| Area | Technologies |
|---|---|
| API | Python 3.13, FastAPI, Pydantic v2, Uvicorn |
| Persistence | PostgreSQL 15, SQLAlchemy 2 async, asyncpg, Alembic |
| Authentication | JWT, Argon2, rotating refresh-token sessions |
| Background processing | Celery, Redis, Celery Beat, Flower |
| Testing | Pytest, pytest-asyncio, HTTPX, pytest-cov |
| Quality and CI | Ruff, pip-audit, GitHub Actions |
| Infrastructure | Docker, Docker Compose |

## Quick start

### Prerequisites

- Git
- Docker Engine or Docker Desktop with Docker Compose

### 1. Clone and configure

```bash
git clone https://github.com/bohdan-tur/booking-app.git
cd booking-app
cp .env.example .env
```

Replace the placeholder database password, signing keys, demo-user passwords,
SMTP credentials, and Flower credentials in `.env`. Generate two different
signing secrets:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

### 2. Start and verify the stack

```bash
docker compose up -d --build
docker compose ps
curl http://localhost:8001/system/ready
```

Compose waits for PostgreSQL, applies `alembic upgrade head`, and starts the
API, Redis, Celery worker, and Celery Beat.

| Service | Address |
|---|---|
| Swagger UI | <http://localhost:8001/docs> |
| ReDoc | <http://localhost:8001/redoc> |
| Readiness probe | <http://localhost:8001/system/ready> |
| PostgreSQL | `localhost:5436` |
| Redis | `localhost:6381` |

Flower is optional and protected with basic authentication:

```bash
docker compose --profile monitoring up -d flower
```

It is then available at <http://localhost:5555>.

Stop the stack without deleting volumes:

```bash
docker compose down
```

Add `-v` only when you intentionally want to remove PostgreSQL and Redis data.

## Demo users

The supplied `.env.example` enables development seed accounts for the three
roles. Seeding is idempotent and uses the passwords configured in `.env`:

- administrator;
- manager;
- regular user.

Set `SEED_DEFAULT_USERS=false` after the initial seed when the accounts are no
longer needed. Production configuration rejects enabled demo-user seeding.

## Configuration

The complete template is available in [`.env.example`](.env.example).

| Variable | Purpose | Development value |
|---|---|---|
| `ENVIRONMENT` | Runtime profile | `development` |
| `DEBUG` | FastAPI debug mode | `false` |
| `DATABASE_URL` | Async PostgreSQL DSN | URL for the `db` service |
| `TEST_DATABASE_URL` | Isolated test DSN | URL for `db_test` |
| `REDIS_URL` | Celery and rate-limit storage | `redis://redis:6379/0` |
| `SECRET_KEY` | Access-token signing key | unique 32+ byte secret |
| `REFRESH_SECRET_KEY` | Refresh-token signing key | different 32+ byte secret |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access-token lifetime | `15` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Refresh-token lifetime | `7` |
| `SEED_DEFAULT_USERS` | Enable development seed | `true` in the template |
| `SMTP_*`, `EMAIL_FROM` | Email transport | provider settings |
| `TIMEZONE` | Celery scheduling timezone | `UTC` |
| `FLOWER_BASIC_AUTH` | Flower credentials | `admin:strong-password` |

Production startup rejects debug mode, demo-user seeding, default or equal
signing keys, and signing keys shorter than 32 bytes.

## API overview

Collection endpoints use stable ascending ID ordering. Paginated endpoints
accept `offset` and `limit` (`20` by default, `100` maximum).

### Authentication and users

| Method | Endpoint | Access | Purpose |
|---|---|---|---|
| `POST` | `/auth/register` | Public | Register an account |
| `POST` | `/auth/login` | Public | Issue access and refresh tokens |
| `POST` | `/auth/refresh` | Refresh token | Rotate the session token |
| `POST` | `/auth/logout` | Refresh token | Revoke one session |
| `POST` | `/auth/logout-all` | Authenticated | Revoke every session |
| `GET` | `/users/me` | Authenticated | Read the current profile |
| `PATCH` | `/users/me/password` | Authenticated | Change the password |
| `GET` | `/users/` | Manager/Admin | List users |
| `PATCH` | `/users/{user_id}/role` | Admin | Change a non-admin role |

### Rooms and bookings

| Method | Endpoint | Access | Purpose |
|---|---|---|---|
| `GET` | `/rooms/all` | Public | List active room types |
| `GET` | `/rooms/available` | Public | Search availability for a period |
| `POST` | `/rooms/` | Admin | Create a room type |
| `PATCH` | `/rooms/{room_id}` | Manager/Admin | Update a room type |
| `DELETE` | `/rooms/{room_id}` | Admin | Archive without deleting history |
| `POST` | `/bookings/` | Authenticated | Create a booking |
| `GET` | `/bookings/` | Manager/Admin | List bookings |
| `GET` | `/bookings/{booking_id}` | Owner/Manager/Admin | Read a booking |
| `PATCH` | `/bookings/{booking_id}` | Manager/Admin | Change an active period |
| `DELETE` | `/bookings/{booking_id}` | Owner/Manager/Admin | Cancel a booking |
| `GET` | `/system/live` | Public | Liveness probe |
| `GET` | `/system/ready` | Public | PostgreSQL readiness probe |

The complete interactive contract and request schemas are available through
Swagger UI at <http://localhost:8001/docs>.

## Example booking

Register or log in, then send a timezone-aware period:

```bash
curl -X POST http://localhost:8001/bookings/ \
  -H "Authorization: Bearer <access-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "room_id": 1,
    "start_time": "2030-08-15T14:00:00Z",
    "end_time": "2030-08-20T11:00:00Z"
  }'
```

When every unit is occupied during any part of the requested interval, the API
returns `409 Conflict`. Naive datetimes, past starts, and invalid ranges are
rejected.

## Authentication and abuse protection

- Access and refresh tokens use different signing secrets and token types.
- Refresh tokens are stored only as SHA-256 hashes.
- Rotation locks the session row, preventing concurrent token reuse.
- Logout supports revoking one session or every session.
- Password changes and account deactivation invalidate existing credentials.
- Every authenticated request reloads and validates the active user.
- Redis limits login by IP and account, and registration and refresh by IP.
- Rate-limit failures return `429` with a `Retry-After` header.
- Redis rate-limit outages fail open for authentication and log no credentials.

## Background processing

Celery Beat schedules:

- completion of finished active bookings every hour;
- reminders for bookings starting the next day at `09:00`;
- a daily booking report for administrators at `23:59`.

Booking creation and cancellation enqueue email notifications. Temporary SMTP
and connection errors retry up to three times with exponential backoff and
jitter. A queue outage after a committed booking does not roll back the booking
itself.

## Testing and quality

The suite uses a dedicated PostgreSQL container because row locking and race
behavior cannot be represented faithfully by an in-memory database.

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

The suite covers authentication, refresh rotation, negative authorization,
booking lifecycle, cancelled-booking availability, room archival, Celery retry
behavior, and real PostgreSQL races. Concurrency scenarios include 20
simultaneous attempts against one- and three-unit inventory, competing creates
and updates, and concurrent refresh-token reuse.

Install the development requirements before running local quality commands:

```bash
python -m pip install -r requirements-dev.txt
ruff check .
ruff format --check .
pip-audit -r requirements.txt
```

GitHub Actions checks Ruff, dependency vulnerabilities, the full migration
lifecycle, tests, Compose validity, and runtime/test image builds.

## Database migrations

Migrations run automatically in Compose. Manual commands:

```bash
docker compose run --rm alembic alembic current
docker compose run --rm alembic alembic upgrade head
```

CI verifies `upgrade -> downgrade base -> upgrade` and checks for schema changes
that are missing a migration.

## Project structure

```text
booking-app/
|-- app/
|   |-- api/                  # Dependencies and routers
|   |-- core/                 # Settings, security, and logging
|   |-- db/                   # Async engine, sessions, and seed
|   |-- models/               # SQLAlchemy models
|   |-- schemas/              # Pydantic contracts
|   |-- services/             # Booking, session, email, and rate-limit logic
|   |-- workers/              # Celery application and tasks
|   |-- alembic/              # Migration environment and revisions
|   `-- main.py               # FastAPI application
|-- tests/                    # API, security, concurrency, and worker tests
|-- .github/workflows/ci.yaml # Continuous integration
|-- docker-compose.yaml
|-- Dockerfile
|-- .env.example
|-- requirements.txt
`-- requirements-dev.txt
```

## Author

**Bohdan Turevych**

- GitHub: [@bohdan-tur](https://github.com/bohdan-tur)
- LinkedIn: [Bohdan Turevych](https://www.linkedin.com/in/bohdan-turevych)

