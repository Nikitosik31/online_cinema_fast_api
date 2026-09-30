from fastapi import FastAPI
from routes import (
    accounts_router,
    admin_router,
    movies_router,
    moderator_movies_router,
)

app = FastAPI()

app.include_router(accounts_router)
app.include_router(admin_router)
app.include_router(moderator_movies_router)
app.include_router(movies_router)
