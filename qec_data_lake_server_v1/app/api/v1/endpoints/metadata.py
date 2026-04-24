from fastapi import APIRouter

router = APIRouter()

@router.get("/")
def list_metadata():
    return {"message": "List metadata"}
