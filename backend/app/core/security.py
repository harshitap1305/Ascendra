from datetime import datetime, timedelta, timezone
import bcrypt
from jose import JWTError, jwt
from app.config import settings


# ── Password hashing ──────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8")[:72], bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8")[:72], hashed.encode("utf-8"))
    except Exception:
        return False


# ── JWT ───────────────────────────────────────────────────────────────────────

def create_access_token(subject: str) -> str:
    """Create a JWT with `sub` = user_id string."""
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> str:
    """Decode JWT and return the subject (user_id). Raises JWTError on failure."""
    payload = jwt.decode(
        token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
    )
    sub: str | None = payload.get("sub")
    if sub is None:
        raise JWTError("Token missing subject")
    return sub
