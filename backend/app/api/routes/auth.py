from fastapi import APIRouter
from pymongo.errors import DuplicateKeyError

from app.schemas.auth import SignupRequest, LoginRequest, TokenResponse, UserResponse
from app.models.user import User
from app.core.security import hash_password, verify_password, create_access_token
from app.core.exceptions import ConflictError, UnauthorizedError
from app.api.deps import get_current_user
from fastapi import Depends

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=TokenResponse, status_code=201)
async def signup(body: SignupRequest):
    try:
        user = User(
            name=body.name,
            email=body.email,
            password_hash=hash_password(body.password),
        )
        await user.insert()
    except DuplicateKeyError:
        raise ConflictError("Email already registered")

    token = create_access_token(str(user.id))
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest):
    user = await User.find_one(User.email == body.email)
    if not user or not verify_password(body.password, user.password_hash):
        raise UnauthorizedError("Invalid email or password")

    token = create_access_token(str(user.id))
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    return UserResponse(
        id=str(current_user.id),
        name=current_user.name,
        email=current_user.email,
        timezone=current_user.timezone,
    )
