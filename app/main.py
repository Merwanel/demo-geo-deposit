"""demo-geo-deposit FastAPI application."""

import logging

from fastapi import FastAPI

from app.routers import deposits

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="demo-geo-deposit")
app.include_router(deposits.router)
