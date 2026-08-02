from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from beanie import PydanticObjectId

from app.core.security import decode_access_token
from app.core.exceptions import UnauthorizedError, NotFoundError
from app.models.user import User
from app.models.exam import Exam

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    try:
        user_id = decode_access_token(token)
    except JWTError:
        raise UnauthorizedError("Invalid or expired token")

    user = await User.get(PydanticObjectId(user_id))
    if user is None:
        raise UnauthorizedError("User not found")
    return user


async def get_exam_for_user(
    exam_id: str,
    current_user: User = Depends(get_current_user),
) -> Exam:
    """Fetch an exam and verify it belongs to current_user. Returns 404 on any mismatch."""
    exam = await Exam.get(PydanticObjectId(exam_id))
    if exam is None or exam.user_id != current_user.id:
        raise NotFoundError("Exam not found")
    return exam
