from app.nlp.analyzer import communication_score, extract_keywords, preprocess, relevance_score, reasoning_score


def test_preprocess_removes_stopwords():
    assert "the" not in preprocess("The quick brown fox")


def test_relevant_beats_irrelevant():
    q = "How do database indexes work and when can they hurt performance?"
    good = ("Indexes are data structures such as B-trees that speed up lookups on a column. They can hurt "
            "write performance because every insert must update the index, and too many indexes waste memory.")
    bad = "I really enjoy hiking on weekends and cooking pasta with my family at home."
    assert relevance_score(q, good) > relevance_score(q, bad)


def test_empty_answer_scores_zero():
    assert relevance_score("Explain Docker", "") == 0.0
    assert communication_score("") == 0.0


def test_reasoning_markers_raise_score():
    structured = "First I check logs, then I isolate the service because errors started after deploy. For example rollback."
    assert reasoning_score(structured) > reasoning_score("dunno")


def test_keywords():
    assert "docker" in extract_keywords("Docker containers package Docker images", 3)
