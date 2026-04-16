from fastapi import APIRouter
from ..services.file_service import list_tasks

router = APIRouter()


@router.get("/tasks")
def tasks():
    return {"tasks": list_tasks()}
