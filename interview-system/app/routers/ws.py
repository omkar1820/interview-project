import secrets

from fastapi import APIRouter, Query, WebSocket

from ..agents.orchestrator import InterviewSession
from ..database import in_db
from ..models import Interview

router = APIRouter()


@router.websocket("/ws/interview/{interview_id}")
async def interview_ws(ws: WebSocket, interview_id: int, token: str = Query(...)):
    stored = await in_db(lambda db: (lambda iv: iv.access_token if iv else None)(db.get(Interview, interview_id)))
    if not stored or not secrets.compare_digest(token, stored):
        await ws.close(code=4401)
        return
    await ws.accept()
    await InterviewSession(interview_id).run(ws)
    try:
        await ws.close()
    except RuntimeError:
        pass
