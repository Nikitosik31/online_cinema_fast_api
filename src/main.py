from fastapi import FastAPI
from routes import accounts_router
app = FastAPI()

app.include_router(accounts_router)
