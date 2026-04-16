from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from ..services.file_service import get_questions, save_answer

router = APIRouter()


class AnswerRequest(BaseModel):
    answer: str


@router.get("/questions")
def questions():
    return get_questions()


@router.post("/questions/answer")
def answer_question(body: AnswerRequest):
    try:
        archived = save_answer(body.answer)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except LookupError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return {"ok": True, "questions_archived": archived}
