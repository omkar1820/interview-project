from typing import Dict, List

from ..models import Response

STRONG, OK = 0.75, 0.55


def aggregate(responses: List[Response]) -> Dict:
    n = max(1, len(responses))
    avg = lambda attr: round(sum(getattr(r, attr) for r in responses) / n, 4)  # noqa: E731
    fields = ("technical_score", "relevance_score", "problem_solving_score", "communication_score", "overall_score")
    t, r, p, c, o = (avg(a) for a in fields)
    labels = {"technical knowledge": t, "answer relevance": r, "problem solving": p, "communication": c}
    strengths = [k for k, v in labels.items() if v >= 0.7] or [max(labels, key=labels.get)]
    improve = [k for k, v in labels.items() if v < 0.6] or ["none significant"]
    if o >= STRONG:
        rec = "Shortlist for next round"
    elif o >= OK:
        rec = "Hold for recruiter review"
    else:
        rec = "Not recommended at this stage"
    return {"overall_score": o, "technical_score": t, "relevance_score": r, "problem_solving_score": p,
            "communication_score": c, "strengths": ", ".join(strengths), "improvements": ", ".join(improve),
            "recommendation": rec}
