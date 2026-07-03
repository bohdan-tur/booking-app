# 🏨 Booking App

![Python](https://img.shields.io/badge/Python-3.13-blue?logo=python\&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.121.1-green?logo=fastapi\&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-blue?logo=postgresql\&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-7-red?logo=redis\&logoColor=white)
![Celery](https://img.shields.io/badge/Celery-5.3.4-37814A?logo=celery\&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0.44-D71F00?logo=sqlalchemy\&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Containerized-2496ED?logo=docker\&logoColor=white)
![GitHub Actions](https://img.shields.io/badge/GitHub%20Actions-CI-success?logo=githubactions\&logoColor=white)

A modern **RESTful hotel booking API** built with **FastAPI**, **PostgreSQL**, **Redis**, and **Celery**.
The project uses an asynchronous architecture, background task processing, JWT-based authentication, isolated testing, database migrations, and a fully containerized development workflow with **Docker Compose**.

---

## 📚 Table of Contents

* [Overview](#overview)
* [Features](#features)
* [Tech Stack](#tech-stack)
* [Architecture](#architecture)
* [Project Structure](#project-structure)
* [Environment Variables](#environment-variables)
* [Docker Services](#docker-services)
* [Getting Started](#getting-started)
* [API Usage Example](#api-usage-example)
* [Testing](#testing)
* [Background Tasks](#background-tasks)
* [Authentication](#authentication)
* [Author](#author)

---

## 📋 Overview

**Booking App** is a backend application for hotel room booking. It is designed as an asynchronous API service with a modular structure, background task processing, and isolated test infrastructure.

The project includes:

* JWT-based authentication with access and refresh tokens
* room booking management endpoints
* PostgreSQL integration with async SQLAlchemy
* Redis-backed Celery task processing
* Alembic database migrations
* isolated Docker-based test setup
* Flower monitoring for Celery tasks

---

## ✨ Features

* 🔐 **JWT Authentication**

  * access and refresh tokens
  * configurable expiration settings
  * token-based protected endpoints

* 🔒 **Password Security**

  * password hashing with **Argon2**
  * password verification via `passlib`

* 🏨 **Booking Management**

  * create and manage room bookings
  * request validation with Pydantic schemas
  * separated business logic layer

* 📨 **Asynchronous Email Notifications**

  * background email sending with Celery
  * SMTP configuration support
  * task monitoring via Flower

* 🗄 **Database Migrations**

  * Alembic-based schema versioning
  * migration support inside Docker workflow

* 🧪 **Isolated Test Environment**

  * dedicated PostgreSQL test container
  * separate test database URL
  * containerized test execution with Pytest

* 🐳 **Containerized Development**

  * multi-service Docker Compose setup
  * separate containers for API, database, Redis, Celery, and tests
  * health checks for dependent services

---

## 🛠 Tech Stack

### Backend

* **Python 3.13**
* **FastAPI 0.121.1**
* **Pydantic 2.12.4**
* **Pydantic Settings 2.13.1**
* **Uvicorn 0.38.0**

### Database & ORM

* **PostgreSQL 15**
* **SQLAlchemy 2.0.44**
* **Alembic 1.17.2**
* **asyncpg 0.31.0**

### Authentication & Security

* **PyJWT 2.12.1**
* **passlib 1.7.4**
* **argon2-cffi 25.1.0**

### Background Tasks & Messaging

* **Celery 5.3.4**
* **Redis 7** — broker / cache server
* **redis-py 5.0.1** — Python Redis client
* **Flower 2.0.1**

### Testing

* **Pytest 9.0.1**
* **pytest-asyncio 1.3.0**
* **httpx 0.28.1**

### DevOps & Tooling

* **Docker**
* **Docker Compose**
* **GitHub Actions**
* **python-dotenv**
* **watchfiles**

---

## 🏗 Architecture

The project runs as a multi-container application and separates responsibilities across dedicated services.

### Main services

* **backend** — FastAPI application
* **db** — primary PostgreSQL database
* **db_test** — isolated PostgreSQL database for tests
* **redis** — broker/cache used by Celery
* **alembic** — migration runner
* **celery_worker** — asynchronous task worker
* **celery_beat** — scheduler for periodic tasks
* **flower** — Celery monitoring UI
* **tests** — dedicated test container

### High-level flow

```text
Client
  ↓
FastAPI Backend
  ├── PostgreSQL (application data)
  ├── Redis (broker / cache)
  └── Celery
       ├── Worker
       ├── Beat
       └── Flower
```

### Startup flow

```text
db + redis
   ↓
alembic migrations
   ↓
backend startup
   ↓
celery worker / beat / flower
```

This allows the application to wait for infrastructure readiness before starting the API.

---

## 📁 Project Structure

```text
booking-app/
├── app/                              # Main application package
│   ├── __init__.py
│   ├── main.py                       # FastAPI entry point
│   │
│   ├── api/                          # API layer
│   │   ├── __init__.py
│   │   ├── dependencies.py           # FastAPI dependencies
│   │   └── routers/                  # Route modules / endpoints
│   │
│   ├── core/                         # Configuration, logging, security
│   │   ├── __init__.py
│   │   ├── config.py                 # Environment-based settings
│   │   ├── logger.py                 # Logger setup
│   │   ├── logging_config.py         # Logging configuration
│   │   └── security.py               # JWT, password hashing, token logic
│   │
│   ├── db/                           # Database layer
│   │   ├── __init__.py
│   │   ├── database.py               # Engine, session, async DB setup
│   │   └── seed.py                   # Seed data
│   │
│   ├── models/                       # SQLAlchemy ORM models
│   │   ├── __init__.py
│   │   ├── user_model.py
│   │   ├── booking_model.py
│   │   ├── room_model.py
│   │   └── role_model.py
│   │
│   ├── schemas/                      # Pydantic schemas / validation
│   │   ├── __init__.py
│   │   ├── user_schema.py
│   │   ├── booking_schema.py
│   │   ├── room_schema.py
│   │   └── token_schema.py
│   │
│   ├── services/                     # Business logic
│   │   ├── __init__.py
│   │   ├── email.py                  # Email service
│   │   └── booking_check.py          # Booking validation/check logic
│   │
│   ├── workers/                      # Celery tasks
│   │   ├── __init__.py
│   │   ├── app.py                    # Celery application instance
│   │   └── tasks.py                  # Background tasks
│   │
│   └── alembic/                      # Database migrations
│       ├── env.py
│       ├── script.py.mako
│       └── versions/
│
├── tests/                            # Test suite
│   ├── __init__.py
│   ├── conftest.py                   # Pytest fixtures
│   ├── test_auth.py
│   ├── test_bookings.py
│   ├── test_rooms.py
│   └── test_users.py
│
├── logs/                             # Application logs
├── .github/                          # GitHub Actions workflows
├── .env.example                      # Example environment variables
├── .gitignore
├── .dockerignore
├── Dockerfile                        # Docker image
├── docker-compose.yaml               # Multi-container orchestration
├── alembic.ini                       # Alembic configuration
├── pytest.ini                        # Pytest configuration
└── requirements.txt
```

---

## ⚙️ Environment Variables

Example configuration:

```env
# Database Configuration
DATABASE_URL=postgresql+asyncpg://postgres:your_db_password@booking_db:5432/booking_db
TEST_DATABASE_URL=postgresql+asyncpg://postgres:password@db_test:5432/test_db
REDIS_URL=redis://redis:6379/0

# Security Configuration
ALGORITHM=HS256
SECRET_KEY=your-secret-key-change-this-in-production
REFRESH_SECRET_KEY=your-refresh-secret-key-change-this-in-production

# Token Expiration
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# Email Configuration
SMTP_HOST=sandbox.smtp.mailtrap.io
SMTP_PORT=587
SMTP_USER=your_mailtrap_user
SMTP_PASSWORD=your_mailtrap_password
EMAIL_FROM=noreply@booking.com

# PostgreSQL Container Configuration
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_db_password
POSTGRES_DB=booking_db

# Application Settings
DEBUG=true
TESTING=false
```

### Key variables

| Variable                      | Description                       |
| ----------------------------- | --------------------------------- |
| `DATABASE_URL`                | Main PostgreSQL connection string |
| `TEST_DATABASE_URL`           | Database used during tests        |
| `REDIS_URL`                   | Redis connection string           |
| `SECRET_KEY`                  | Secret key for access tokens      |
| `REFRESH_SECRET_KEY`          | Secret key for refresh tokens     |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access token lifetime             |
| `REFRESH_TOKEN_EXPIRE_DAYS`   | Refresh token lifetime            |
| `SMTP_HOST` / `SMTP_PORT`     | SMTP server configuration         |
| `SMTP_USER` / `SMTP_PASSWORD` | SMTP credentials                  |
| `EMAIL_FROM`                  | Default sender email              |
| `DEBUG`                       | Enables debug mode                |
| `TESTING`                     | Enables test mode                 |

---

## 🐳 Docker Services

The application is designed to run using Docker Compose.

| Service         | Purpose                                         |
| --------------- | ----------------------------------------------- |
| `db`            | Main PostgreSQL database                        |
| `redis`         | Redis broker / cache                            |
| `alembic`       | Runs database migrations before backend startup |
| `backend`       | FastAPI application                             |
| `db_test`       | Separate PostgreSQL container for tests         |
| `celery_worker` | Executes background tasks                       |
| `celery_beat`   | Runs scheduled Celery tasks                     |
| `flower`        | Web UI for Celery monitoring                    |
| `tests`         | Runs the Pytest suite                           |

---

## 🚀 Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/bohdan-tur/booking-app.git
cd booking-app
```

### 2. Create the environment file

```bash
cp .env.example .env
```

Then update the `.env` file with your local configuration.

### 3. Start all services

```bash
docker compose up -d --build
```

This command will build and start:

* PostgreSQL
* Redis
* Alembic migrations
* FastAPI backend
* Celery worker
* Celery beat
* Flower

### 4. Check service status

```bash
docker compose ps
```

---

## 🌐 Available Services

Once the application is running, the following endpoints should be available:

| Service    | URL                           |
| ---------- | ----------------------------- |
| Swagger UI | `http://localhost:8001/docs`  |
| ReDoc      | `http://localhost:8001/redoc` |
| Flower     | `http://localhost:5555`       |
| PostgreSQL | `localhost:5432`              |
| Redis      | `localhost:6379`              |

---

## 💻 API Usage Example

### Create a booking

**Request**

`POST /api/v1/bookings/`

```json
{
  "room_id": 101,
  "start_time": "2026-08-15T14:00:00Z",
  "end_time": "2026-08-20T12:00:00Z"
}
```

**Response — `201 Created`**

```json
{
  "id": 42,
  "room_id": 101,
  "user_id": 5,
  "start_time": "2026-08-15T14:00:00Z",
  "end_time": "2026-08-20T12:00:00Z",
  "status": "Booked"
}
```

---

## 🧪 Testing

The project uses a **separate PostgreSQL test container** to keep tests isolated from development data.

### Run tests

```bash
docker compose run --rm tests
```

### Test setup

The `tests` service:

* waits for `db_test` to become healthy
* uses `TEST_DATABASE_URL`
* runs the full Pytest suite inside Docker
* remains isolated from the main application database

This makes the test workflow reproducible and independent of the local machine environment.

---

## 📬 Background Tasks

Background processing is handled with **Celery** and **Redis**.

### Included services

* **celery_worker** — executes asynchronous tasks
* **celery_beat** — schedules periodic jobs
* **flower** — provides a monitoring dashboard for task execution

Typical use cases for background tasks include:

* sending email notifications
* processing long-running jobs outside the request/response cycle
* scheduling recurring tasks

---

## 🔐 Authentication

The application uses **JWT-based authentication** with separate settings for access and refresh tokens.

### Authentication configuration

```env
ALGORITHM=HS256
SECRET_KEY=your-secret-key
REFRESH_SECRET_KEY=your-refresh-secret-key
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7
```

### Supported token types

* **access token** — short-lived token for protected requests
* **refresh token** — longer-lived token used to issue a new access token

Passwords are hashed using **Argon2** via `passlib`.

---

## 👨‍💻 Author

**Bohdan Turevych**

* GitHub: [@bohdan-tur](https://github.com/bohdan-tur)
* LinkedIn: **Bohdan Turevych**
