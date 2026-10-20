import json
import logging
import re
from typing import Dict

from ..config import get_settings
from ..nlp.analyzer import (clamp, communication_score, extract_keywords, length_factor,
                            reasoning_score, relevance_score)
from .llm import ask, make_agent

log = logging.getLogger("evaluator")

SYSTEM = (
    "You are a strict, fair interview evaluator. Score the candidate's answer to the question for the given "
    "role. Respond with ONLY a JSON object with keys: technical_knowledge, answer_relevance, problem_solving, "
    "communication (each a float 0-1), and feedback (max 2 sentences, constructive). Judge only the content "
    "of the answer: ignore the candidate's name, gender, accent, or any personal attributes."
)

WEIGHTS = {"technical": 0.35, "relevance": 0.25, "problem_solving": 0.20, "communication": 0.20}


def overall(t: float, r: float, p: float, c: float) -> float:
    return round(WEIGHTS["technical"] * t + WEIGHTS["relevance"] * r
                 + WEIGHTS["problem_solving"] * p + WEIGHTS["communication"] * c, 4)


class EvaluatorAgent:
    """Analyses relevance (NLP) + quality (LLM), produces a score and feedback."""

    def __init__(self):
        self.use_llm = get_settings().use_llm
        self.agent = make_agent("Evaluator", SYSTEM, 0.1) if self.use_llm else None

    async def evaluate(self, role: str, question: str, answer: str) -> Dict:
        nlp_rel = relevance_score(question, answer)
        nlp_comm = communication_score(answer)
        nlp_ps = reasoning_score(answer)
        # offline estimate of technical depth: relevance + reasoning + enough substance
        nlp_tech = clamp(0.55 * nlp_rel + 0.25 * nlp_ps + 0.20 * length_factor(answer, 60))
        feedback = self._offline_feedback(answer, nlp_rel, nlp_comm, nlp_ps)
        scores = {"technical": nlp_tech, "relevance": nlp_rel, "problem_solving": nlp_ps,
                  "communication": nlp_comm}

        if self.agent is not None:
            try:
                prompt = (f"Role: {role}\nQuestion: {question}\nCandidate answer: {answer[:3000]}\n"
                          "Return the JSON now.")
                data = self._parse(await ask(self.agent, prompt))
                scores["technical"] = clamp(0.8 * data["technical_knowledge"] + 0.2 * nlp_tech)
                scores["relevance"] = clamp(0.5 * data["answer_relevance"] + 0.5 * nlp_rel)
                scores["problem_solving"] = clamp(0.8 * data["problem_solving"] + 0.2 * nlp_ps)
                scores["communication"] = clamp(0.7 * data["communication"] + 0.3 * nlp_comm)
                feedback = str(data.get("feedback") or feedback)[:600]
            except Exception as exc:
                log.warning("Evaluator LLM failed, using NLP-only scores: %s", exc)

        t, r, p, c = (round(scores[k], 4) for k in ("technical", "relevance", "problem_solving", "communication"))
        return {"technical": t, "relevance": r, "problem_solving": p, "communication": c,
                "overall": overall(t, r, p, c), "feedback": feedback}

    @staticmethod
    def _parse(text: str) -> Dict:
        m = re.search(r"\{.*\}", text or "", re.S)
        data = json.loads(m.group(0) if m else "{}")
        for k in ("technical_knowledge", "answer_relevance", "problem_solving", "communication"):
            data[k] = clamp(float(data[k]))
        return data

    @staticmethod
    def _offline_feedback(answer: str, rel: float, comm: float, ps: float) -> str:
        notes = []
        if len(answer.split()) < 25:
            notes.append("Answer is brief; add more detail and a concrete example.")
        if rel < 0.4:
            notes.append("Stay closer to what the question asks.")
        if ps < 0.4:
            notes.append("Explain your reasoning step by step.")
        if comm < 0.45:
            notes.append("Structure the answer in clearer, shorter sentences.")
        if not notes:
            kws = ", ".join(extract_keywords(answer, 3))
            notes.append(f"Clear and relevant answer covering {kws}." if kws else "Clear and relevant answer.")
        return " ".join(notes[:2])
