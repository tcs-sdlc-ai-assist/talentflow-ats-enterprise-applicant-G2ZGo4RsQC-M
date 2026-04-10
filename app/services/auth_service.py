import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_password, verify_password
from app.models.user import User

logger = logging.getLogger(__name__)


async def register_user(
    db: AsyncSession,
    username: str,
    password: str,
    full_name: str,
    email: str,
    role: str = "Interviewer",
) -> User:
    """Register a new user with the given details.

    Creates a user with the Interviewer role by default.
    Raises ValueError if username or email already exists.
    """
    existing_username = await db.execute(
        select(User).where(User.username == username)
    )
    if existing_username.scalar_one_or_none() is not None:
        raise ValueError(f"Username '{username}' is already taken")

    existing_email = await db.execute(
        select(User).where(User.email == email)
    )
    if existing_email.scalar_one_or_none() is not None:
        raise ValueError(f"Email '{email}' is already registered")

    hashed = hash_password(password)

    user = User(
        username=username,
        hashed_password=hashed,
        full_name=full_name,
        email=email,
        role=role,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    logger.info("Registered new user: username=%s, role=%s", username, role)
    return user


async def login_user(
    db: AsyncSession,
    username: str,
    password: str,
) -> Optional[User]:
    """Verify credentials and return the user if valid.

    Returns None if the username does not exist, the password is wrong,
    or the account is inactive.
    """
    result = await db.execute(
        select(User).where(User.username == username)
    )
    user = result.scalar_one_or_none()

    if user is None:
        logger.warning("Login failed: user '%s' not found", username)
        return None

    if not user.is_active:
        logger.warning("Login failed: user '%s' is inactive", username)
        return None

    if not verify_password(password, user.hashed_password):
        logger.warning("Login failed: invalid password for user '%s'", username)
        return None

    logger.info("User '%s' logged in successfully", username)
    return user


async def seed_admin(db: AsyncSession) -> Optional[User]:
    """Create the default admin account on startup if it does not exist.

    Uses DEFAULT_ADMIN_USERNAME and DEFAULT_ADMIN_PASSWORD from settings.
    Returns the admin user if created, or None if it already exists.
    """
    result = await db.execute(
        select(User).where(User.username == settings.DEFAULT_ADMIN_USERNAME)
    )
    existing = result.scalar_one_or_none()

    if existing is not None:
        logger.info(
            "Default admin user '%s' already exists, skipping seed",
            settings.DEFAULT_ADMIN_USERNAME,
        )
        return None

    hashed = hash_password(settings.DEFAULT_ADMIN_PASSWORD)

    admin = User(
        username=settings.DEFAULT_ADMIN_USERNAME,
        hashed_password=hashed,
        full_name="System Administrator",
        email=f"{settings.DEFAULT_ADMIN_USERNAME}@talentflow.local",
        role="System Admin",
        is_active=True,
    )
    db.add(admin)
    await db.flush()
    await db.refresh(admin)

    logger.info(
        "Default admin user '%s' created successfully",
        settings.DEFAULT_ADMIN_USERNAME,
    )
    return admin