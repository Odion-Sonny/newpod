# NEWPOD Escrow Platform

NEWPOD is an enterprise-grade escrow platform designed to protect buyers and sellers on social commerce platforms such as Instagram, Facebook, WhatsApp, and TikTok. Rather than transferring money directly, transactions run through NEWPOD, which holds buyer funds securely until delivery is verified and the inspection window passes.

This project is built using **Clean Architecture** and **Domain-Driven Design (DDD)** principles to ensure scalability, security, and maintainability.

---

## 🏗️ Project Architecture & Layout

The codebase is organized according to Clean Architecture layers to isolate the business domain logic from external frameworks, database implementations, and presentation layers.

```
newpod/
├── docker-compose.yml       # Orchestrates services (DB, Redis, Backend, Celery)
├── backend/                 # Python FastAPI Backend
│   ├── Dockerfile
│   ├── pyproject.toml       # Python dependencies (managed by uv)
│   ├── uv.lock              # Lockfile for reproducible builds
│   ├── alembic.ini          # Database migration config
│   ├── alembic/             # Database migrations
│   ├── src/                 # Application source code
│   │   ├── main.py          # FastAPI application entrypoint
│   │   ├── core/            # App settings, database session setup, telemetry, security
│   │   ├── domain/          # Entities & repository interfaces (pure business contracts)
│   │   ├── use_cases/       # Core business logic / application orchestrators
│   │   └── adapters/        # Interface adapters (controllers, DB repositories, API schemas, external gateways)
│   └── tests/               # Pytest integration & unit test suites
```

### Key Architectural Layers

1. **Domain Layer (`backend/src/domain/`)**: Holds the core repository definitions. It remains agnostic of how data is stored or retrieved.
2. **Use Cases Layer (`backend/src/use_cases/`)**: Encapsulates all application-specific business rules and coordinates workflows (e.g., creating an order, transitioning an escrow status, handling disputes).
3. **Adapters Layer (`backend/src/adapters/`)**: Concrete implementations of external components.
   - **`db/`**: Concrete SQLAlchemy repositories (e.g., [`SQLAlchemyEscrowRepository`](backend/src/adapters/db/repositories/escrow_repository.py)) and ORM models ([`models.py`](backend/src/adapters/db/models.py)).
   - **`api/`**: API endpoints/controllers (e.g., [`controllers/escrow.py`](backend/src/adapters/api/controllers/escrow.py)) and Pydantic schemas.
   - **`gateways/`**: Client wrappers for external platforms (e.g., [`PaystackClient`](backend/src/adapters/gateways/paystack.py)).
4. **Core Layer (`backend/src/core/`)**: Cross-cutting concerns such as application settings/config ([`config.py`](backend/src/core/config.py)), security utils ([`security.py`](backend/src/core/security.py)), database engines ([`database.py`](backend/src/core/database.py)), and metrics/logs telemetry ([`telemetry.py`](backend/src/core/telemetry.py)).

---

## 🌟 Core Features

- **🔐 Robust Authentication**: Supports email/phone credentials, JWT token exchange, and refresh token rotation with strict session management.
- **🛡️ Escrow Engine**: State machine backing full buyer/seller verification lifecycle states (`CREATED`, `PENDING_PAYMENT`, `PAYMENT_SECURED`, `SELLER_ACCEPTED`, `PACKED`, `SHIPPED`, `DELIVERED`, `INSPECTION_WINDOW`, `RELEASED`, `REFUNDED`, `CANCELLED`, `DISPUTED`).
- **💰 Wallet Ledger (Double-Entry Bookkeeping)**: A precise financial sub-system (`debit`/`credit`) logging transactions (`ESCROW_PAYMENT`, `ESCROW_RELEASE`, `SETTLEMENT`, `REFUND`, `DEPOSIT`, `WITHDRAWAL`) to ensure an audit trail.
- **💳 Payment Integration**: Native support for **Paystack** checkout initialization, transaction verification, payout transfers, and secure webhook signature verification.
- **💬 Real-Time Chat**: WebSockets connection manager orchestrating direct conversations between buyers and sellers, supporting typing states, attachments, and read receipts.
- **⚖️ Dispute Resolution**: Evidence upload (photo/video/docs) with tamper-resistant SHA-256 hashes, dispute logs, timeline trails, and admin manual overrides.
- **📈 Telemetry**: Integrated OpenTelemetry instrumentation, custom logging, and Prometheus endpoints for metrics collection.

---

## 🛠️ Technology Stack

- **Backend**: FastAPI, SQLAlchemy 2.0 (Asyncpg), Alembic, Pydantic v2
- **Database / Cache**: PostgreSQL, Redis
- **Background Tasks**: Celery
- **DevOps**: Docker, Docker Compose, GitHub Actions
- **Testing**: Pytest (with pytest-asyncio and pytest-cov)

---

## 🚀 Getting Started

### Prerequisites
- Python 3.12+ (or 3.14 recommended per environment settings)
- [uv](https://github.com/astral-sh/uv) (Astral Python Package Manager)
- Docker & Docker Compose

### Running with Docker Compose

To start the entire services stack (PostgreSQL, Redis, FastAPI Backend, Celery Worker):

```bash
docker compose up --build
```

The backend server runs at `http://localhost:8000`. You can inspect the interactive OpenAPI docs at `http://localhost:8000/api/v1/docs`.

---

## 💻 Local Development Setup (Manual)

If you prefer to run services manually for debugging:

### 1. Set Up Environment Variables
Configure your database credentials in your environment or a `.env` file within the `backend` folder. By default, it looks for:
```ini
DATABASE_URL=postgresql+asyncpg://newpod_user:newpod_secure_password@localhost:5433/newpod_db
REDIS_URL=redis://localhost:6380/0
SECRET_KEY=super_secure_secret_key_change_me_in_prod_12345
PAYSTACK_SECRET_KEY=sk_test_mock_secret_key_for_development
```

### 2. Install Dependencies
Make sure you are in the `backend` directory, then use `uv` to install dependencies and configure the virtual environment:
```bash
uv sync
```

### 3. Run Database Migrations
Execute the migrations against your local database instance:
```bash
uv run alembic upgrade head
```

### 4. Start the Development Server
```bash
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

### 5. Start the Celery Worker
For asynchronous background processing:
```bash
uv run celery -A src.core.celery_app worker --loglevel=info
```

---

## 🧪 Running Tests

The test suite runs against a transaction-wrapped instance of the database to guarantee test isolation.

Run all tests:
```bash
uv run pytest
```

Generate test coverage reports:
```bash
uv run pytest --cov=src --cov-report=term-missing
```
