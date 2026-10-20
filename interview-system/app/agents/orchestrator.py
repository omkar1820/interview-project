import asyncio
import logging

from fastapi import WebSocket, WebSocketDisconnect

from ..config import get_settings
from ..database import in_db
from ..models import FinalResult, Interview, Response, utcnow
from ..services.scoring import aggregate
from .candidate_proxy import CandidateProxy
from .evaluator import EvaluatorAgent
from .interviewer import InterviewerAgent

log = logging.getLogger("orchestrator")


class InterviewSession:
    """Runs the loop: Interviewer -> Candidate Proxy -> Evaluator -> persist -> next question."""

    def __init__(self, interview_id: int):
        self.interview_id = interview_id
        self.interviewer = InterviewerAgent()
        self.evaluator = EvaluatorAgent()

    # ---- DB units of work (run in a thread) ----
    def _load(self, db):
        iv = db.get(Interview, self.interview_id)
        history = [(r.question_text, r.answer_text) for r in iv.responses]
        return {"role": iv.role, "name": iv.candidate.name, "total": iv.num_questions,
                "status": iv.status, "history": history}

    def _mark_started(self, db):
        iv = db.get(Interview, self.interview_id)
        if iv.status == "pending":
            iv.status, iv.started_at = "in_progress", utcnow()
            db.commit()

    def _save_response(self, db, order_no, question, answer, ev):
        db.add(Response(
            interview_id=self.interview_id, order_no=order_no, question_text=question, answer_text=answer,
            technical_score=ev["technical"], relevance_score=ev["relevance"],
            problem_solving_score=ev["problem_solving"], communication_score=ev["communication"],
            overall_score=ev["overall"], feedback=ev["feedback"]))
        db.commit()

    def _finalize(self, db):
        iv = db.get(Interview, self.interview_id)
        data = aggregate(list(iv.responses))
        if iv.result is None:
            db.add(FinalResult(interview_id=iv.id, **data))
        iv.status, iv.completed_at = "completed", utcnow()
        db.commit()
        return data

    # ---- main loop ----
    async def run(self, ws: WebSocket) -> None:
        ctx = await in_db(self._load)
        proxy = CandidateProxy(ws, get_settings().answer_timeout_seconds)
        if ctx["status"] == "completed":
            await proxy.notify({"type": "complete", "message": "This interview is already completed."})
            return
        await in_db(self._mark_started)
        history, total = ctx["history"], ctx["total"]
        await proxy.notify({"type": "welcome", "name": ctx["name"], "role": ctx["role"], "total": total,
                            "resumed_at": len(history)})
        try:
            for idx in range(len(history) + 1, total + 1):
                question = await self.interviewer.next_question(ctx["role"], history, idx, total)
                answer = await proxy.ask(idx, total, question)
                await proxy.notify({"type": "evaluating"})
                ev = await self.evaluator.evaluate(ctx["role"], question, answer)
                await in_db(lambda db: self._save_response(db, idx, question, answer, ev))
                history.append((question, answer))
            await in_db(self._finalize)
            await proxy.notify({"type": "complete",
                                "message": "Thank you! Your interview is complete. A recruiter will be in touch."})
        except WebSocketDisconnect:
            log.info("Candidate disconnected from interview %s (can resume)", self.interview_id)
        except asyncio.TimeoutError:
            log.info("Interview %s timed out waiting for an answer", self.interview_id)
            await proxy.notify({"type": "timeout", "message": "Session timed out. Reconnect to resume."})
