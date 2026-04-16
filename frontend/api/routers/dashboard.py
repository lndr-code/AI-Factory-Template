from fastapi import APIRouter
from ..services.file_service import get_report_content

router = APIRouter()


@router.get("/dashboard")
def dashboard():
    return get_report_content()
