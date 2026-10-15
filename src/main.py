from fastapi import FastAPI
from routes import (
    accounts_router,
    admin_router,
    movies_router,
    moderator_movies_router,
)
from routes.interactions import (
    favorites_router,
    ratings_router,
    reactions_router,
    comments_router,
    notifications_router,
)

app = FastAPI()

app.include_router(accounts_router)
app.include_router(admin_router)
app.include_router(moderator_movies_router)
app.include_router(favorites_router)
app.include_router(movies_router)
app.include_router(reactions_router)
app.include_router(ratings_router)
app.include_router(comments_router)
app.include_router(notifications_router)
