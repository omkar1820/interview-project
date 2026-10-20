import asyncio
from typing import Any, Dict

from fastapi import WebSocket


class CandidateProxy:
    """Communication bridge between the candidate's browser (WebSocket) and the agent loop."""

    MAX_ANSWER_CHARS = 4000

    def __init__(self, ws: WebSocket, timeout: int):
        self.ws = ws
        self.timeout = timeout

    async def notify(self, payload: Dict[str, Any]) -> None:
        await self.ws.send_json(payload)

    async def ask(self, index: int, total: int, question: str) -> str:
        await self.notify({"type": "question", "index": index, "total": total, "text": question})
        while True:
            msg = await asyncio.wait_for(self.ws.receive_json(), timeout=self.timeout)
            text = str(msg.get("text", "")).strip() if isinstance(msg, dict) else ""
            if msg.get("type") == "answer" and text:
                return text[: self.MAX_ANSWER_CHARS]
            await self.notify({"type": "error", "message": "Please type an answer before submitting."})
