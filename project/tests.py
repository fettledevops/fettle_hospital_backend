import time

import jwt

from project.jwt_auth import create_token


def test_create_token_contains_payload_fields():
    payload = {"user_id": "u1", "email": "u@example.com", "role": "Admin"}
    token = create_token(payload.copy(), timeout=2)
    decoded = jwt.decode(
        token, options={"verify_signature": False, "verify_exp": False}
    )
    assert decoded["user_id"] == "u1"
    assert decoded["email"] == "u@example.com"
    assert decoded["role"] == "Admin"
    assert "exp" in decoded


def test_create_token_respects_timeout_window():
    before = int(time.time())
    token = create_token(
        {"user_id": "u2", "email": "x@y.com", "role": "user"}, timeout=1
    )
    after = int(time.time())
    decoded = jwt.decode(
        token, options={"verify_signature": False, "verify_exp": False}
    )
    assert before + 55 <= decoded["exp"] <= after + 65
