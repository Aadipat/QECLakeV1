from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.zenodo_service import ZenodoService
import requests


router = APIRouter(prefix="/zenodo", tags=["Zenodo Discovery"])


class ZenodoRegisterPayload(BaseModel):
    record: dict[str, Any]


@router.get("/search")
def search_zenodo(q: str, size: int = 10):
    service = ZenodoService()

    try:
        results = service.search_records(query=q, size=size)
        return {
            "query": q,
            "results": results,
        }
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Zenodo request failed: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/register")
def register_zenodo_record(payload: ZenodoRegisterPayload):
    service = ZenodoService()

    try:
        return service.register_record(payload.record)
    except KeyError as e:
        raise HTTPException(status_code=400, detail=f"Missing field in Zenodo record: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))