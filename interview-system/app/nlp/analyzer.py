"""Lightweight NLP layer: preprocessing, keyword extraction, TF-IDF cosine relevance, heuristics."""
import re
from collections import Counter
from typing import List

from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

_TOKEN = re.compile(r"[a-zA-Z][a-zA-Z0-9+#.\-]{1,}")
REASONING_MARKERS = (
    "because", "therefore", "so that", "first", "then", "next", "finally", "trade-off", "tradeoff",
    "however", "for example", "for instance", "approach", "step", "result", "reason", "if ", "otherwise",
)


def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(x)))


def preprocess(text: str) -> List[str]:
    """Clean + tokenize: lowercase, strip stop-words."""
    return [t for t in (m.lower().strip(".-") for m in _TOKEN.findall(text or ""))
            if t and t not in ENGLISH_STOP_WORDS]


def extract_keywords(text: str, top_n: int = 8) -> List[str]:
    return [w for w, _ in Counter(preprocess(text)).most_common(top_n)]


def relevance_score(question: str, answer: str) -> float:
    """TF-IDF cosine similarity between question and answer, rescaled to a usable 0-1 range
    and combined with a length-adequacy factor (very short answers cannot be fully relevant)."""
    if not preprocess(answer):
        return 0.0
    try:
        vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
        m = vec.fit_transform([question, answer])
        cos = float(cosine_similarity(m[0], m[1])[0][0])
    except ValueError:
        cos = 0.0
    q_terms = set(preprocess(question))
    coverage = len(q_terms & set(preprocess(answer))) / max(1, len(q_terms))
    base = clamp(0.55 * min(1.0, cos * 2.5) + 0.45 * min(1.0, coverage * 1.8))
    return clamp(base * length_factor(answer, full_at=40))


def length_factor(answer: str, full_at: int = 40) -> float:
    words = len((answer or "").split())
    return clamp(0.25 + 0.75 * words / full_at)


def communication_score(answer: str) -> float:
    """Heuristic clarity score: adequate length, sentence structure, lexical variety."""
    words = (answer or "").split()
    if not words:
        return 0.0
    sentences = [s for s in re.split(r"[.!?\n]+", answer) if s.strip()]
    avg_len = len(words) / max(1, len(sentences))
    structure = 1.0 if 8 <= avg_len <= 28 else 0.6 if avg_len < 8 or avg_len <= 40 else 0.4
    diversity = len({w.lower() for w in words}) / len(words)
    return clamp(0.45 * length_factor(answer, 50) + 0.30 * structure + 0.25 * min(1.0, diversity * 1.4))


def reasoning_score(answer: str) -> float:
    """Heuristic problem-solving signal: structured reasoning markers + examples."""
    low = (answer or "").lower()
    hits = sum(1 for m in REASONING_MARKERS if m in low)
    return clamp(0.25 * length_factor(answer, 60) + 0.75 * min(1.0, hits / 4))
