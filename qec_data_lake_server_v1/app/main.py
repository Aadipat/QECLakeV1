from fastapi import FastAPI
from app.api.v1.router import api_router
from app.core.sqlite_database import init_db



# backend
app = FastAPI(title="QEC Data Lake Server v1")

# Run the sqlite db
init_db()

app.include_router(api_router, prefix="/api/v1")
