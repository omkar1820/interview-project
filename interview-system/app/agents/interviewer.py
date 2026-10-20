import logging
from typing import List, Tuple

from ..config import get_settings
from ..nlp.analyzer import extract_keywords
from .llm import ask, make_agent

log = logging.getLogger("interviewer")

SYSTEM = (
    "You are a professional technical interviewer conducting a first-round screening interview. "
    "Ask exactly ONE clear, concise question per turn. Start with fundamentals, then probe deeper "
    "using the candidate's previous answers (follow-ups). Never reveal scores or evaluate. "
    "Output only the question text."
)

BANKS = {
    "data": [
        "Walk me through how you would clean and validate a messy dataset before analysis.",
        "Explain the difference between INNER JOIN, LEFT JOIN and a window function, with a use case for each.",
        "How would you find the top 3 customers by revenue per region using SQL?",
        "How do you decide which metric to present to a non-technical stakeholder?",
        "Describe a time an analysis changed a decision. What was your approach?",
        "How would you detect and handle outliers in a dataset?",
    ],
    "devops": [
        "Explain how a CI/CD pipeline should be structured for a containerised service.",
        "How would you design a highly available web application on AWS?",
        "What is the difference between a Docker image and a container, and how do you keep images small and secure?",
        "How do you manage secrets and configuration across environments?",
        "Walk me through how you would troubleshoot a service that suddenly returns 5xx errors.",
        "How would you implement monitoring, alerting and rollback for deployments?",
    ],
    "software": [
        "Explain the difference between a process and a thread, and when you would use each.",
        "How would you design a REST API for a booking system? Cover resources, errors and versioning.",
        "What strategies do you use to write testable, maintainable code?",
        "Describe how database indexes work and when they can hurt performance.",
        "How would you debug a memory leak in a production service?",
        "Explain how you would handle concurrency and race conditions in a shared resource.",
    ],
    "default": [
        "Tell me about your most relevant experience for this role.",
        "Describe a difficult technical problem you solved and your approach.",
        "How do you prioritise tasks when everything seems urgent?",
        "How do you keep your skills current in your field?",
        "Tell me about a mistake you made and what you learned.",
        "How do you explain complex ideas to people without your background?",
    ],
}


def _bank_for(role: str) -> List[str]:
    r = role.lower()
    if any(k in r for k in ("data", "analyst", "bi ", "analytics")):
        return BANKS["data"]
    if any(k in r for k in ("devops", "cloud", "sre", "infrastructure", "platform")):
        return BANKS["devops"]
    if any(k in r for k in ("software", "developer", "engineer", "backend", "frontend", "full")):
        return BANKS["software"]
    return BANKS["default"]


class InterviewerAgent:
    """Generates questions, controls interview flow and asks follow-ups."""

    def __init__(self):
        self.use_llm = get_settings().use_llm
        self.agent = make_agent("Interviewer", SYSTEM, 0.6) if self.use_llm else None

    async def next_question(self, role: str, history: List[Tuple[str, str]], idx: int, total: int) -> str:
        if self.agent is not None:
            try:
                convo = "\n".join(f"Q{i + 1}: {q}\nA{i + 1}: {a[:600]}" for i, (q, a) in enumerate(history))
                prompt = (
                    f"Role being interviewed for: {role}\nThis is question {idx} of {total}.\n"
                    f"Conversation so far:\n{convo or '(none yet)'}\n\n"
                    "Ask the next question. Do not repeat earlier questions."
                )
                q = await ask(self.agent, prompt)
                if q:
                    return q.strip().strip('"')
            except Exception as exc:
                log.warning("Interviewer LLM failed, falling back: %s", exc)
        return self._offline_question(role, history, idx)

    @staticmethod
    def _offline_question(role: str, history: List[Tuple[str, str]], idx: int) -> str:
        bank = _bank_for(role)
        if history and len(history[-1][1].split()) < 20 and idx % 2 == 0:
            kws = extract_keywords(history[-1][1], 2)
            topic = " and ".join(kws) if kws else "that"
            return f"Could you go deeper on {topic}? Give a concrete example from your experience."
        used = {q for q, _ in history}
        for q in bank:
            if q not in used:
                return q
        return bank[(idx - 1) % len(bank)]
