SUPER = {"X-API-Key": "test-key"}


def bearer(c, email, pw):
    r = c.post("/api/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["token"]}


def test_agency_seats_and_recruiter_scoping(client):
    ag = client.post("/api/admin/agencies", headers=SUPER, json={"name": "Acme Staffing", "max_recruiters": 1}).json()
    assert client.post("/api/admin/agencies", headers=SUPER, json={"name": "Acme Staffing"}).status_code == 409

    def mk(e):
        return client.post("/api/admin/recruiters", headers=SUPER,
                           json={"agency_id": ag["id"], "name": "R", "email": e, "password": "password123"})

    assert mk("r1@acme.com").status_code == 200
    assert mk("r2@acme.com").status_code == 409  # seat limit
    other = client.post("/api/admin/agencies", headers=SUPER, json={"name": "Beta HR"}).json()
    assert client.post("/api/admin/recruiters", headers=SUPER, json={
        "agency_id": other["id"], "name": "B", "email": "b@beta.com", "password": "password123"}).status_code == 200

    h1, h2 = bearer(client, "r1@acme.com", "password123"), bearer(client, "b@beta.com", "password123")
    iid = client.post("/api/interviews", headers=h1, json={
        "name": "Asha", "email": "asha@x.com", "role": "QA", "num_questions": 1}).json()["interview_id"]
    assert len(client.get("/api/interviews", headers=h1).json()) == 1
    assert client.get("/api/interviews", headers=h2).json() == []
    assert client.get(f"/api/interviews/{iid}/report", headers=h2).status_code == 404
    assert client.get(f"/api/interviews/{iid}/transcript", headers=h1).status_code == 200
    assert client.get("/api/admin/agencies", headers=h1).status_code == 403
    assert client.get("/api/interviews", headers=SUPER).json()[0]["recruiter_name"] == "R"


def test_login_rules(client):
    assert client.post("/api/auth/login", json={"email": "nope@x.com", "password": "bad"}).status_code == 401
    assert client.post("/api/auth/login", json={"api_key": "test-key"}).json()["role"] == "super_admin"
    t = client.post("/api/auth/login", json={"api_key": "test-key"}).json()["token"]
    assert client.get("/api/admin/agencies", headers={"Authorization": "Bearer " + t}).status_code == 200
    assert client.get("/api/admin/agencies", headers={"Authorization": "Bearer " + t[:-3] + "xyz"}).status_code == 401


def test_disabled_recruiter_is_locked_out(client):
    ag = client.post("/api/admin/agencies", headers=SUPER, json={"name": "Gamma"}).json()
    r = client.post("/api/admin/recruiters", headers=SUPER, json={
        "agency_id": ag["id"], "name": "G", "email": "g@gamma.com", "password": "password123"}).json()
    h = bearer(client, "g@gamma.com", "password123")
    client.patch(f"/api/admin/recruiters/{r['id']}", headers=SUPER, json={"active": False})
    assert client.get("/api/interviews", headers=h).status_code == 401
