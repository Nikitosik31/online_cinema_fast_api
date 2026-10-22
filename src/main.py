"""Application entry point: creates the FastAPI app and registers all routers."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from database.database import seed_db
from routes import (
    accounts_router,
    movies_router,
    cart_router,
    orders_router,
    docs_router,
    payments_router,
)
from routes.staff import (
    admin_router,
    moderator_movies_router,
    moderator_router,
)
from routes.interactions import (
    favorites_router,
    ratings_router,
    reactions_router,
    comments_router,
    notifications_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Run code at application startup and shutdown.

    On startup it seeds the reference data (user groups and certifications).
    Database tables are created separately by Alembic migrations. Nothing is
    needed on shutdown.

    Args:
        app (FastAPI): The application instance.
    """
    await seed_db()
    yield


tags_metadata = [
    {
        "name": "Accounts",
        "description": "Registration, activation, login, token refresh and password reset.",
    },
    {
        "name": "Movies",
        "description": "Public movie catalog: list, search, filters and movie details.",
    },
    {
        "name": "Favorites",
        "description": "The current user's favorite movies.",
    },
    {"name": "Ratings", "description": "Rating movies from 1 to 10."},
    {
        "name": "Reactions",
        "description": "Likes and dislikes on movies and comments.",
    },
    {"name": "Comments", "description": "Movie comments and replies."},
    {
        "name": "Notifications",
        "description": "Notifications about replies and likes on the user's comments.",
    },
    {"name": "Cart", "description": "The current user's shopping cart."},
    {
        "name": "Orders",
        "description": "Placing, listing and canceling orders.",
    },
    {"name": "Admin", "description": "Administrator-only user management."},
    {
        "name": "Moderator: Movies",
        "description": "Movie catalog management (create, update, delete).",
    },
    {
        "name": "Moderator: Carts, Orders & Payments",
        "description": "Moderator views of users' carts and orders.",
    },
]


API_DESCRIPTION = """
**Online Cinema** is a REST API for a movie streaming platform: a movie catalog, user interaction with it, and a shopping cart with orders.

## What you can do

* **Accounts**: register, activate the account by email, log in and reset the password.
* **Movies**: browse the catalog with search, filtering and sorting.
* **Interaction**: favorites, ratings, comments with replies, likes and dislikes, and notifications about replies and likes.
* **Shopping**: put movies in the cart and place an order.
* **Staff tools**: managing movies, users, carts and orders.

## Authentication

Most endpoints require a JWT access token. Log in to get one, then send it in the `Authorization` header as `Authorization: Bearer <access_token>`.

The access token is valid for 60 minutes. Use the refresh endpoint to get a new one without logging in again.

## Roles

| Role | Access |
|------|--------|
| **User** | Own profile, favorites, ratings, comments, cart and orders |
| **Moderator** | Everything a user can do, plus movie management and viewing carts and orders |
| **Admin** | Everything a moderator can do, plus user management |

## Conventions

* List endpoints are paginated with the `page` and `per_page` query parameters and return `prev_page` and `next_page` links.
* Errors are returned as JSON: `{"detail": "Description of the problem"}`.
* Prices are decimal numbers and are returned as strings, for example `"9.99"`.
"""


app = FastAPI(
    title="Online Cinema API",
    summary="Movie catalog, user interaction, cart and orders.",
    description=API_DESCRIPTION,
    version="1.0.0",
    lifespan=lifespan,
    openapi_tags=tags_metadata,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

app.include_router(accounts_router)
app.include_router(admin_router)
app.include_router(moderator_movies_router)
app.include_router(moderator_router)
app.include_router(favorites_router)
app.include_router(movies_router)
app.include_router(reactions_router)
app.include_router(ratings_router)
app.include_router(comments_router)
app.include_router(notifications_router)
app.include_router(cart_router)
app.include_router(orders_router)
app.include_router(docs_router)
app.include_router(payments_router)
