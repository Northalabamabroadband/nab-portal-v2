from app.core.security import create_session_token, decode_session_token, hash_password, verify_password


def test_password_hashing() -> None:
    value = "CorrectHorseBatteryStaple!"
    hashed = hash_password(value)
    assert hashed != value
    assert verify_password(value, hashed)
    assert not verify_password("wrong-password", hashed)


def test_session_token() -> None:
    token = create_session_token(
        subject="user-1",
        email="admin@nabroadband.com",
        roles=["super_admin"],
        permissions=["admin.manage"],
    )
    claims = decode_session_token(token)
    assert claims["sub"] == "user-1"
    assert "super_admin" in claims["roles"]
