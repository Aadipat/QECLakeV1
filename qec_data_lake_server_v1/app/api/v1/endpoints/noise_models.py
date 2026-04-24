from fastapi import APIRouter

router = APIRouter()

@router.get("/")
def list_noise_models():
    return {"message": "List noise models"}
