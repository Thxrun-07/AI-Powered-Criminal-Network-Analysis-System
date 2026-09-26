import os
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.services.auth_service import AuthService

client = TestClient(app)

@pytest.fixture
def auth_service(tmp_path):
    storage_path = str(tmp_path / "test_users.json")
    return AuthService(storage_path=storage_path)


def test_auth_service_register_and_login(auth_service):
    # Register officer
    session = auth_service.register(
        officer_name="Officer Jane Doe",
        badge_number="IND-LE-9999",
        password="securepass123",
        department="Cyber Forensics & Telecom Analysis",
        clearance_level="Level 2: Field Investigator"
    )
    assert session["officerName"] == "Officer Jane Doe"
    assert session["badgeNumber"] == "IND-LE-9999"

    # Login officer
    login_session = auth_service.login("IND-LE-9999", "securepass123")
    assert login_session["officerName"] == "Officer Jane Doe"
    assert login_session["department"] == "Cyber Forensics & Telecom Analysis"

    # Invalid password
    with pytest.raises(ValueError, match="Invalid passcode"):
        auth_service.login("IND-LE-9999", "wrongpass")

    # Duplicate badge
    with pytest.raises(ValueError, match="already registered"):
        auth_service.register(
            officer_name="Another Officer",
            badge_number="IND-LE-9999",
            password="pass"
        )


import uuid

def test_auth_router_api(monkeypatch, tmp_path):
    test_storage = str(tmp_path / "router_users.json")
    isolated_auth = AuthService(storage_path=test_storage)
    monkeypatch.setattr("backend.routers.auth.auth_service", isolated_auth)

    unique_id = uuid.uuid4().hex[:6].upper()
    unique_badge = f"IND-TEST-{unique_id}"
    unique_name = f"Test Officer {unique_id}"
    # Test signup API
    res = client.post(
        "/api/auth/signup",
        json={
            "officerName": unique_name,
            "badgeNumber": unique_badge,
            "password": "testpass123",
            "department": "Narcotics & Organized Syndicate Bureau",
            "clearanceLevel": "Level 4: Special Director"
        }
    )
    assert res.status_code == 201
    body = res.json()
    assert body["success"] is True
    assert body["session"]["badgeNumber"] == unique_badge

    # Test login API
    login_res = client.post(
        "/api/auth/login",
        json={
            "badgeNumber": unique_badge,
            "password": "testpass123"
        }
    )
    assert login_res.status_code == 200
    login_body = login_res.json()
    assert login_body["success"] is True
    assert login_body["session"]["officerName"] == unique_name

    # Test list users API
    users_res = client.get("/api/auth/users")
    assert users_res.status_code == 200
    assert "users" in users_res.json()
