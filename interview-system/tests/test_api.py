import pytest

H = {"X-API-Key": "test-key"}


def test_health(client):
    assert client.get("/health").json()["database"] is True


def test_admin_key_required(client):
    assert client.get("/api/interviews").status_code == 401


def test_full_interview_flow(client):
    r = client.post("/api/interviews", headers=H, json={
        "name": "Asha Rao", "email": "asha@example.com", "role": "Data Analyst", "num_questions": 2})
    assert r.status_code == 200
    d = r.json()
    iid, token = d["interview_id"], d["access_token"]

    assert client.get(f"/api/interviews/{iid}/public", params={"token": "bad"}).status_code == 404

    answer = ("I would first profile the data, then remove duplicates because they skew results, and finally "
              "validate ranges. For example, SQL window functions help rank customers by revenue per region.")
    with client.websocket_connect(f"/ws/interview/{iid}?token={token}") as ws:
        assert ws.receive_json()["type"] == "welcome"
        for i in (1, 2):
            q = ws.receive_json()
            assert q["type"] == "question" and q["index"] == i
            ws.send_json({"type": "answer", "text": answer})
            assert ws.receive_json()["type"] == "evaluating"
        assert ws.receive_json()["type"] == "complete"

    rep = client.get(f"/api/interviews/{iid}/report", headers=H).json()
    assert rep["status"] == "completed" and len(rep["responses"]) == 2
    assert 0 <= rep["result"]["overall_score"] <= 1
    assert client.patch(f"/api/interviews/{iid}/decision", headers=H,
                        json={"decision": "advance"}).status_code == 200
    assert client.get("/api/interviews", headers=H).json()[0]["recruiter_decision"] == "advance"


def test_ws_rejects_bad_token(client):
    from starlette.websockets import WebSocketDisconnect
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/interview/1?token=wrong"):
            pass
