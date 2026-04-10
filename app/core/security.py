import logging
from typing import Optional

from fastapi import Request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings

logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

serializer = URLSafeTimedSerializer(settings.SECRET_KEY)

COOKIE_NAME = "session"
SESSION_MAX_AGE = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_session_cookie(user_id: str, role: str) -> str:
    data = {"user_id": user_id, "role": role}
    return serializer.dumps(data, salt="session-cookie")


def decode_session_cookie(cookie_value: str) -> Optional[dict]:
    try:
        data = serializer.loads(
            cookie_value,
            salt="session-cookie",
            max_age=SESSION_MAX_AGE,
        )
        return data
    except SignatureExpired:
        logger.warning("Session cookie expired")
        return None
    except BadSignature:
        logger.warning("Invalid session cookie signature")
        return None
    except Exception:
        logger.exception("Unexpected error decoding session cookie")
        return None


def create_access_token(data: dict) -> str:
    user_id = data.get("sub", data.get("user_id", ""))
    role = data.get("role", "")
    return create_session_cookie(str(user_id), role)


def decode_access_token(token: str) -> Optional[dict]:
    return decode_session_cookie(token)


async def get_current_user(request: Request) -> Optional["User"]:
    from app.core.database import async_session
    from app.models.user import User

    cookie_value = request.cookies.get(COOKIE_NAME)
    if not cookie_value:
        return None

    session_data = decode_session_cookie(cookie_value)
    if session_data is None:
        return None

    user_id = session_data.get("user_id")
    if not user_id:
        return None

    try:
        async with async_session() as db:
            result = await db.execute(
                select(User).where(User.id == user_id, User.is_active == True)
            )
            user = result.scalar_one_or_none()
            return user
    except Exception:
        logger.exception("Error fetching user from session")
        return None


async def get_current_user_from_session(
    request: Request, db: AsyncSession
) -> Optional["User"]:
    from app.models.user import User

    cookie_value = request.cookies.get(COOKIE_NAME)
    if not cookie_value:
        return None

    session_data = decode_session_cookie(cookie_value)
    if session_data is None:
        return None

    user_id = session_data.get("user_id")
    if not user_id:
        return None

    try:
        result = await db.execute(
            select(User).where(User.id == user_id, User.is_active == True)
        )
        user = result.scalar_one_or_none()
        return user
    except Exception:
        logger.exception("Error fetching user from session")
        return None