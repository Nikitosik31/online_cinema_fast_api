from contextlib import asynccontextmanager

from fastapi import FastAPI

from database.database import seed_db
from routes import (
    accounts_router,
    admin_router,
    movies_router,
    moderator_movies_router,
    cart_router,
)
from routes.interactions import (
    favorites_router,
    ratings_router,
    reactions_router,
    comments_router,
    notifications_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await seed_db()
    yield


app = FastAPI(lifespan=lifespan)

app.include_router(accounts_router)
app.include_router(admin_router)
app.include_router(moderator_movies_router)
app.include_router(favorites_router)
app.include_router(movies_router)
app.include_router(reactions_router)
app.include_router(ratings_router)
app.include_router(comments_router)
app.include_router(notifications_router)
app.include_router(cart_router)
