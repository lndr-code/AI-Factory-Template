from fastapi import APIRouter, HTTPException
from ..services.process_manager import ProcessManager

router = APIRouter()


@router.post("/run/start")
def start_run():
    manager = ProcessManager.get()
    try:
        pid = manager.start()
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return {"started": True, "pid": pid}


@router.get("/run/status")
def run_status():
    return ProcessManager.get().status()
