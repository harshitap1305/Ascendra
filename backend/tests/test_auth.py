import pytest
from jose import JWTError
from app.core.security import hash_password, verify_password, create_access_token, decode_access_token
from app.schemas.auth import SignupRequest, LoginRequest
from pydantic import ValidationError


def test_password_hashing():
    plain = "SuperSecretPassword123!"
    hashed = hash_password(plain)
    assert hashed != plain
    assert verify_password(plain, hashed) is True
    assert verify_password("WrongPassword", hashed) is False


def test_jwt_access_token():
    user_id = "507f1f77bcf86cd799439011"
    token = create_access_token(subject=user_id)
    assert isinstance(token, str)
    assert len(token) > 20
    
    decoded_sub = decode_access_token(token)
    assert decoded_sub == user_id


def test_invalid_jwt_throws():
    with pytest.raises(JWTError):
        decode_access_token("invalid.token.string")


def test_signup_request_schema():
    data = {"name": "Test User", "email": "test@example.com", "password": "password123"}
    req = SignupRequest(**data)
    assert req.email == "test@example.com"

    with pytest.raises(ValidationError):
        SignupRequest(name="No Email", email="invalid-email", password="pwd")
