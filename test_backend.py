import pytest
from server import app

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

def test_login_wrong_password(client):
    res = client.post("/api/login", json={"username": "john_doe", "password": "wrong"})
    assert res.status_code == 401

def test_dashboard_requires_auth(client):
    res = client.get("/api/dashboard/summary")
    assert res.status_code == 401

def test_customer_cannot_delete_transaction(client):
    res_login = client.post("/api/login", json={"username": "john_doe", "password": "password123"})
    assert res_login.status_code == 200
    
    res = client.delete("/api/transactions/1")
    assert res.status_code == 403
