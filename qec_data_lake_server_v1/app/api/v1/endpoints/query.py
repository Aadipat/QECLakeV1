from fastapi import APIRouter

router = APIRouter()

@router.post("/search")
def search():
    return {"message": "Search metadata"}
