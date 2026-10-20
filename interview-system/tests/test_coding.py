import shutil

import pytest

from app.runner import execute
from app.services import problems

SUPER = {"X-API-Key": "test-key"}
PY_OK = ("import sys\nd = sys.stdin.read().split()\nn = int(d[0])\n"
         "print(sum(int(x) for x in d[1:1 + n] if int(x) % 2 == 0))\n")
JS_OK = ("const d = require('fs').readFileSync(0, 'utf8').split(/\\s+/).filter(Boolean).map(Number);\n"
         "console.log(d.slice(1, 1 + d[0]).filter(x => x % 2 === 0).reduce((a, b) => a + b, 0));\n")


def make(client, level="easy", role="Data Analyst"):
    d = client.post("/api/interviews", headers=SUPER, json={
        "name": "Cody", "email": f"cody{make.n}@x.com", "role": role, "num_questions": 1,
        "coding_difficulty": level}).json()
    make.n += 1
    return d["interview_id"], {"token": d["access_token"]}


make.n = 0


def test_reference_solutions_are_consistent():
    for p in problems.PROBLEMS:
        assert len(p["tests"]) >= 4 and p["difficulty"] in ("easy", "medium", "hard")
    assert problems.track_for("Frontend Engineer") == "frontend"
    assert problems.pick_problem("Data Analyst", "easy", 1)["id"] == "sum-evens"


def test_runner_limits():
    assert execute("python", "print(1+1)")["stdout"].strip() == "2"
    assert execute("python", "while True: pass", "", 1.0)["timed_out"] is True
    assert execute("python", "import sys; sys.exit(3)")["exit"] == 3
    big = execute("python", "while True: print('x' * 1000)", "", 2.0)
    assert len(big["stdout"]) <= 64 * 1024
    env = execute("python", "import os; print(sorted(os.environ))")["stdout"]
    assert "OPENAI_API_KEY" not in env and "ADMIN_API_KEY" not in env
    assert execute("ruby", "puts 1")["ok"] is False


def test_coding_flow(client):
    iid, tok = make(client)
    info = client.get(f"/api/interviews/{iid}/coding", params=tok).json()
    assert info["problem"]["id"] == "sum-evens" and len(info["problem"]["samples"]) == 2
    assert "tests" not in info["problem"]
    assert client.get(f"/api/interviews/{iid}/coding", params={"token": "bad"}).status_code == 404
    assert client.get(f"/api/interviews/{iid}/public", params=tok).json()["coding_enabled"] is True

    wrong = client.post(f"/api/interviews/{iid}/coding/run", params=tok, json={"language": "python", "code": "print(0)"})
    assert wrong.json()["passed"] < wrong.json()["total"]
    loop = client.post(f"/api/interviews/{iid}/coding/run", params=tok,
                       json={"language": "python", "code": "while True: pass"}).json()
    assert loop["results"][0]["status"] == "timeout" and loop["results"][1]["status"] == "skipped"

    r = client.post(f"/api/interviews/{iid}/coding/submit", params=tok, json={"language": "python", "code": PY_OK})
    assert r.status_code == 200 and r.json()["passed"] == r.json()["total"] == 5
    assert all("input" not in x for x in r.json()["results"] if not x["visible"])
    assert client.post(f"/api/interviews/{iid}/coding/submit", params=tok,
                       json={"language": "python", "code": PY_OK}).status_code == 409
    rep = client.get(f"/api/interviews/{iid}/report", headers=SUPER).json()
    assert rep["coding"]["passed"] == 5 and rep["coding"]["problem_title"] == "Sum of even numbers"


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_javascript_submission(client):
    iid, tok = make(client)
    r = client.post(f"/api/interviews/{iid}/coding/submit", params=tok, json={"language": "javascript", "code": JS_OK})
    assert r.json()["passed"] == 5


def test_no_coding_round_returns_404(client):
    d = client.post("/api/interviews", headers=SUPER, json={
        "name": "No Code", "email": "nocode@x.com", "role": "QA", "num_questions": 1}).json()
    assert client.get(f"/api/interviews/{d['interview_id']}/coding", params={"token": d["access_token"]}).status_code == 404
