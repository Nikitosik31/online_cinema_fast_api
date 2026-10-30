# Online Cinema API

A REST API for an online movie store, built with **FastAPI** and **async SQLAlchemy**. Users browse a movie catalog, interact with it (favorites, ratings, comments, likes), put movies in a cart, place orders and pay for them through **Stripe**. Staff members (moderators and administrators) manage the catalog, users, carts and payments.

The whole stack (API, PostgreSQL, Redis, Celery worker and scheduler, MailHog, MinIO) starts with a single `docker compose up`.

## Contents

- [Features](#features)
- [Tech stack](#tech-stack)
- [Quick start with Docker](#quick-start-with-docker)
- [Using the API](#using-the-api)
- [Payments with Stripe](#payments-with-stripe)
- [Running without Docker](#running-without-docker)
- [Database migrations](#database-migrations)
- [Running the tests](#running-the-tests)
- [Configuration](#configuration)
- [API overview](#api-overview)
- [How it works](#how-it-works)
- [Project structure](#project-structure)
- [Known limitations](#known-limitations)

## Features

- **Accounts**: registration with email activation, login, logout, JWT access and refresh tokens, password change and password reset by email.
- **Roles**: `user`, `moderator` and `admin`. Admins activate users and change their roles; moderators manage the catalog and see carts, orders and payments.
- **Profile**: name, gender, date of birth and info, plus an **avatar** stored in MinIO (JPEG, PNG or WebP, up to 2 MB).
- **Movie catalog**: pagination, filtering by genre, year and IMDb rating, text search (title, description, actors, directors) and sorting by price, year or popularity.
- **Interaction**: favorites, ratings from 1 to 10, likes and dislikes on movies and comments, threaded comments with replies.
- **Notifications**: a notification is created when someone replies to your comment or likes it. New ones are also **pushed in real time over WebSocket**.
- **Shopping**: cart, orders, Stripe Checkout payment, payment history and refunds.
- **Background jobs**: Celery beat cleans up expired activation and password-reset tokens every 6 hours.
- **Protected documentation**: Swagger UI and ReDoc are available only to moderators and administrators.
- **Tests**: over 300 test functions covering accounts, catalog, interactions, cart, orders, payments, webhooks and the documentation access.

## Tech stack

| Area | Technology |
|------|------------|
| Web framework | FastAPI, Uvicorn |
| Database | PostgreSQL 16, SQLAlchemy 2.0 (async, `asyncpg`), Alembic |
| Validation and settings | Pydantic v2, pydantic-settings |
| Auth | JWT (`python-jose`), password hashing with `passlib` + `bcrypt` |
| Background tasks | Celery (worker and beat), Redis |
| Payments | Stripe (Checkout, webhooks, refunds) |
| Email | `aiosmtplib`, MailHog for development |
| File storage | MinIO (S3-compatible) |
| Tests | pytest, pytest-asyncio, httpx, pytest-cov |
| Packaging and deploy | Poetry, Docker, Docker Compose |

## Quick start with Docker

You need Docker with Docker Compose. Python is not required on your machine for this path.

**1. Clone the repository and create the environment file**

```bash
git clone <repository-url>
cd online_cinema_fast_api
cp .env_sample .env
```

**2. Fill in the values in `.env`**

The file works as it is for a first look at the API. Two things should be changed:

- `POSTGRES_PASSWORD` and `JWT_SECRET_KEY`: set your own. A good secret can be generated with `openssl rand -hex 32`.
- `STRIPE_SECRET_KEY` and `STRIPE_WEBHOOK_SECRET`: put your **test mode** keys from the Stripe dashboard. Without real test keys everything except payments works (see [Payments with Stripe](#payments-with-stripe)).

Inside Docker the hostnames (`db`, `redis`, `mailhog`, `minio`) are set by `docker-compose.yml`, so `POSTGRES_HOST=localhost` and the other `localhost` values in `.env` can stay as they are.

**3. Build and start everything**

```bash
docker compose up --build
```

On start the `app` container applies the database migrations (`alembic upgrade head`) and then starts the API. The application also seeds the user groups and movie certifications and creates the MinIO bucket for avatars.

**4. Create the first administrator**

New accounts are always regular users, so the first administrator is created from the command line. In another terminal:

```bash
docker compose exec app python -m scripts.create_admin
```

The script asks for an email and a password. The password must be at least 8 characters long and contain an uppercase letter, a lowercase letter, a digit and a special character (`@ $ ! % * ? # &`).

**5. Open the documentation**

Go to <http://localhost:8000/docs> and sign in with the administrator's email and password (HTTP Basic authentication prompt of the browser). Only moderators and administrators can open `/docs`, `/redoc` and `/openapi.json`.

### Services and ports

| Service | Address | Purpose |
|---------|---------|---------|
| API and Swagger UI | <http://localhost:8000/docs> | The application |
| MailHog | <http://localhost:8025> | Catches all outgoing emails (activation, password reset, payment confirmation) |
| MinIO console | <http://localhost:9001> | Browse the stored avatars (login and password are `MINIO_ACCESS_KEY` and `MINIO_SECRET_KEY` from `.env`) |
| MinIO API | <http://localhost:9000> | Public URLs of avatars |
| PostgreSQL | `localhost:5432` | Database |
| Redis | `localhost:6379` | Celery broker and result backend |

### Useful commands

```bash
docker compose up -d                 # start in the background
docker compose logs -f app           # follow the API logs
docker compose down                  # stop, keep the data
docker compose down -v               # stop and DELETE the database and stored files
```

## Using the API

### 1. Register and activate an account

1. Send `POST /register/` with an email and a password.
2. Open MailHog at <http://localhost:8025>: the activation email is there.
3. Copy the `token` from the link in the email and send it to `POST /activate/` as `{"token": "..."}`.
4. Send `POST /login/`. The response contains an `access_token` (valid for 60 minutes) and a `refresh_token` (valid for 7 days).

### 2. Authorize in Swagger

Click **Authorize** in Swagger UI and paste the `access_token` (without the word `Bearer`). Protected endpoints now work. Use `POST /refresh/` to get a new access token without logging in again.

### 3. Fill the catalog (moderator or admin)

The catalog starts empty. Log in as the administrator and create genres (`POST /movies/genres/`), stars (`POST /movies/stars/`) and movies (`POST /movies/`). The movie certifications are created automatically.

### 4. Buy a movie

1. `POST /cart/items/` adds a movie to the cart.
2. `POST /orders/` creates an order from the cart.
3. `POST /payments/checkout/` returns a Stripe payment page link.
4. After a successful payment the Stripe webhook marks the order as paid, clears the bought movies from the cart and sends a confirmation email.

Other roles: an administrator can promote a user with `PATCH /admin/users/{user_id}/group/` and activate or deactivate accounts with `PATCH /admin/users/{user_id}/activate/`.

## Payments with Stripe

The payment is confirmed by a **webhook**, not by the request that starts it, so Stripe must be able to reach your local server. For development use the [Stripe CLI](https://stripe.com/docs/stripe-cli):

```bash
stripe listen --forward-to localhost:8000/payments/webhook/
```

The command prints a signing secret that starts with `whsec_`. Put it into `STRIPE_WEBHOOK_SECRET` in `.env` and restart the `app` container. Pay on the Stripe page with the test card `4242 4242 4242 4242` (any future expiry date and any CVC).

The webhook handles three events:

| Stripe event | What happens |
|--------------|--------------|
| `checkout.session.completed` | A payment is recorded, the order becomes `paid`, the cart is cleared of the bought movies, a confirmation email is sent |
| `checkout.session.expired` | A payment with the `canceled` status is recorded; the order stays pending, so the user can try to pay again |
| `charge.refunded` | The payment becomes `refunded` and the order becomes `canceled` |

**Refunds.** The owner of a successful payment requests a full refund with `POST /payments/{payment_id}/refund/`. The endpoint answers `202 Accepted` right away; the money is returned and the statuses change only when Stripe sends the `charge.refunded` event.

## Running without Docker

Use this path when you want to run the API on your machine with auto-reload. You need Python 3.14 and [Poetry](https://python-poetry.org/) 2.x.

**1. Start the infrastructure in Docker** (everything except the application):

```bash
docker compose up -d db redis mailhog minio
```

**2. Install the dependencies and activate the environment**

```bash
poetry install
```

**3. Make sure `.env` points to `localhost`** (this is the default in `.env_sample`), then apply the migrations from the project root:

```bash
alembic upgrade head
```

**4. Start the API** from the `src` directory:

```bash
cd src
uvicorn main:app --reload
```

**5. Start Celery** in two more terminals, also from `src`:

```bash
celery -A celery_app worker --loglevel=info
celery -A celery_app beat --loglevel=info
```

**6. Create the administrator** from the `src` directory:

```bash
python -m scripts.create_admin
```

## Database migrations

Tables are created by Alembic, not by the application. Migrations are in `alembic/versions`.

```bash
alembic upgrade head                                  # apply all migrations
alembic revision --autogenerate -m "describe change"  # create a migration after changing models
alembic downgrade -1                                  # roll back the last migration
```

In Docker the migrations are applied automatically every time the `app` container starts. Run Alembic commands from the project root. To run them inside the container, use `docker compose exec app alembic ...`.

## Running the tests

The tests use a **separate PostgreSQL database**, so they never touch your development data. Emails and Stripe calls are replaced with mocks, so no external services are needed.

**1. Create the test database** (PostgreSQL must be running):

```bash
docker compose exec db psql -U postgres -c "CREATE DATABASE movies_db_test;"
```

**2. Create `.env.test`** next to `.env`. It has the same variables as `.env`, but with `POSTGRES_DB=movies_db_test` and `POSTGRES_HOST=localhost`. The file is in `.gitignore`.

**3. Run the tests** from the project root:

```bash
poetry run pytest
```

With a coverage report:

```bash
poetry run pytest --cov=src --cov-report=html
```

Do not run two test sessions at the same time: they share one test database.

## Configuration

All settings are environment variables read from `.env` (see `.env_sample`). **Every variable is required**: the application does not start if one is missing, and unknown variables in `.env` are rejected.

| Variable | Description |
|----------|-------------|
| `POSTGRES_DB`, `POSTGRES_DB_PORT`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST` | PostgreSQL connection |
| `JWT_SECRET_KEY` | Secret used to sign access tokens |
| `REDIS_HOST`, `REDIS_PORT` | Redis, used as the Celery broker and result backend |
| `SMTP_HOST`, `SMTP_PORT` | SMTP server for outgoing email (MailHog in development) |
| `STRIPE_SECRET_KEY` | Stripe secret API key, test mode (`sk_test_...`) |
| `STRIPE_WEBHOOK_SECRET` | Secret that verifies webhook requests come from Stripe (`whsec_...`) |
| `MINIO_ENDPOINT` | MinIO address used by the application, `host:port` without a scheme |
| `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY` | MinIO credentials (also the MinIO root user and password in Docker Compose) |
| `MINIO_BUCKET` | Bucket for avatars |
| `MINIO_PUBLIC_URL` | Base URL that browsers use to open stored files, without a trailing slash |

When the application runs in Docker Compose, `docker-compose.yml` overrides the hostnames (`POSTGRES_HOST`, `REDIS_HOST`, `SMTP_HOST`, `MINIO_ENDPOINT`) with the service names, so the same `.env` works both inside and outside Docker.

## API overview

The full, interactive description with request and response examples is in Swagger UI (`/docs`). Lists are paginated with `page` and `per_page` (at most 20 per page) and errors look like `{"detail": "..."}`. Prices are returned as strings, for example `"9.99"`.

| Group | Endpoints | Access |
|-------|-----------|--------|
| **Accounts** | `POST /register/`, `/activate/`, `/activate/resend/`, `/login/`, `/logout/`, `/refresh/`, `/change_password/`, `/password_reset/request/`, `/password_reset/confirm/` | Public, `change_password` needs a login |
| **Profile** | `GET /profile/`, `PATCH /profile/`, `PUT /profile/avatar/`, `DELETE /profile/avatar/` | Logged-in user |
| **Movies** | `GET /movies/`, `GET /movies/{movie_id}/`, `GET /movies/genres/` | Public |
| **Favorites** | `POST` and `DELETE /movies/{movie_id}/favorite/`, `GET /movies/favorites/` | Logged-in user |
| **Ratings** | `PUT`, `DELETE`, `GET /movies/{movie_id}/rating/` | Logged-in user |
| **Reactions** | `PUT`, `DELETE /movies/{movie_id}/reaction/` | Logged-in user |
| **Comments** | `POST`, `GET /movies/{movie_id}/comments/`, `DELETE .../comments/{comment_id}/`, `PUT`, `DELETE .../comments/{comment_id}/reaction/` | Logged-in user |
| **Notifications** | `GET /notifications/`, `PATCH /notifications/{notification_id}/read/`, WebSocket `/notifications/ws/` | Logged-in user |
| **Cart** | `POST /cart/items/`, `GET /cart/`, `DELETE /cart/items/{movie_id}/`, `DELETE /cart/` | Logged-in user |
| **Orders** | `POST /orders/`, `GET /orders/`, `POST /orders/{order_id}/cancel/` | Logged-in user |
| **Payments** | `POST /payments/checkout/`, `GET /payments/`, `POST /payments/{payment_id}/refund/`, `POST /payments/webhook/`, `GET /payments/success/`, `GET /payments/cancel/` | Logged-in user (webhook is called by Stripe) |
| **Moderator: Movies** | `POST`, `PATCH`, `DELETE` for `/movies/`, `/movies/genres/` and `/movies/stars/` | Moderator, admin |
| **Moderator: Carts, Orders & Payments** | `GET /moderator/carts/{user_id}/`, `GET /moderator/orders/`, `GET /moderator/payments/` | Moderator, admin |
| **Admin** | `PATCH /admin/users/{user_id}/activate/`, `PATCH /admin/users/{user_id}/group/` | Admin |
| **Documentation** | `GET /docs`, `/redoc`, `/openapi.json` | Moderator, admin (HTTP Basic) |

### Roles

| Role | Access |
|------|--------|
| **User** | Own profile, favorites, ratings, comments, cart and orders |
| **Moderator** | Everything a user can do, plus movie management and viewing carts, orders and payments |
| **Admin** | Everything a moderator can do, plus user management |

## How it works

### Real-time notifications (WebSocket)

Connect to `ws://localhost:8000/notifications/ws/?token=<access_token>`. The token goes in the query string because browsers cannot set the `Authorization` header for a WebSocket. If the token is invalid or expired, the server closes the connection with code `1008` before accepting it.

While you are connected, the server sends one JSON message for every new notification (a reply to your comment or a like on it), in the same format as the items of `GET /notifications/`. Notifications created while you are offline are not pushed: fetch them with `GET /notifications/`. WebSocket endpoints do not appear in Swagger, so they are described here and in the API description.

### Avatars

An avatar is uploaded with `PUT /profile/avatar/` as `multipart/form-data` (field `file`). The type is checked (`415` for anything but JPEG, PNG and WebP), then the size (`413` above 2 MB). The file is stored in the MinIO bucket under a random name, so every upload gets a new URL and browsers never show a cached old picture. The database stores only the object key; `avatar_url` in the profile response is built from `MINIO_PUBLIC_URL`. The old file is deleted after the new one is saved. The bucket is created on application start and its files are readable by anyone, while uploading and deleting need the MinIO credentials.

### Cart, orders and payments

- A movie can be added to the cart once, only if it has a price and only if the user has not bought it yet.
- An order is created from the cart. Movies that are unavailable or already bought are skipped and listed in `excluded_movies`. The cart stays unchanged until the payment succeeds.
- The payment amount is calculated on the server from the order items, never taken from the request.
- A pending order can be canceled by its owner. A paid order can only be returned through a refund request.

### Deleting a movie

A movie that is part of any order cannot be deleted (`409`), because orders keep the purchase history. If the movie is in users' carts, the request is rejected with a warning unless `?force=true` is passed.

### Background tasks

Celery beat sends the `delete_expired_tokens` task to the worker every 6 hours. It removes activation and password-reset tokens that have expired.

## Project structure

```
.
├── alembic/                 # Database migrations
├── docker-compose.yml       # app, celery worker and beat, db, redis, mailhog, minio
├── Dockerfile               # Image for the app and the Celery services
├── pyproject.toml           # Dependencies (Poetry) and pytest settings
└── src/
    ├── main.py              # App creation, startup (seeding, MinIO bucket), routers
    ├── celery_app.py        # Celery app and beat schedule
    ├── tasks.py             # Background tasks
    ├── config/              # Settings read from .env
    ├── database/            # Engine, sessions, models, validators
    ├── routes/              # Endpoints: accounts, movies, cart, orders, payments, profile, docs
    │   ├── interactions/    # Favorites, ratings, reactions, comments, notifications
    │   └── staff/           # Admin and moderator endpoints
    ├── schemas/             # Pydantic request and response schemas
    ├── security/            # JWT, password hashing, auth dependencies
    ├── notifications/       # Email sending and the WebSocket connection manager
    ├── storage/             # MinIO client for avatars
    ├── scripts/             # create_admin command
    ├── exceptions/          # Custom exceptions
    └── tests/               # pytest tests, grouped by feature
```

## Known limitations

This is a learning project. These are the known gaps, kept deliberately simple:

- **WebSocket works with a single process.** The list of connected users is kept in the memory of the process. With several Uvicorn workers or several app containers, a notification reaches only users connected to the same process; scaling needs Redis pub/sub.
- **The WebSocket token is in the URL**, so it can appear in server and proxy logs. The alternative is to exchange the token for a short-lived one-time ticket first.
- **Default credentials.** MinIO uses `minioadmin` / `minioadmin` and the `.env_sample` values are for development only. Change all secrets before any real deployment.
- **No HTTPS.** The MinIO client uses plain HTTP (`secure=False`), and the containers run as root. Both are fine for local development, not for production.
- **Avatar checks.** The file type is taken from the `Content-Type` sent by the client and the file is read into memory (hence the 2 MB limit). A real service should also inspect the file content.
- **Refunds are full only.** Partial refunds are not supported.
- **Stripe is test mode only.**
