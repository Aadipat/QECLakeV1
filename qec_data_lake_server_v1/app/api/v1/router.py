from fastapi import APIRouter
from app.api.v1.endpoints import metadata, query, generation, noise_models

api_router = APIRouter()

api_router.include_router(metadata.router, prefix="/metadata", tags=["metadata"])
api_router.include_router(query.router, prefix="/query", tags=["query"])
api_router.include_router(generation.router, prefix="/generation", tags=["generation"])
api_router.include_router(noise_models.router, prefix="/noise-models", tags=["noise-models"])
