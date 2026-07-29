from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_access_token
from app.db.database import get_db
from app.models.role_model import Role
from app.models.user_model import Users

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)], db: DbSession
) -> Users:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    user_id_str = verify_access_token(token)
    if not user_id_str:
        raise credentials_exception

    stmt = select(Users).filter(Users.id == int(user_id_str))
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise credentials_exception

    return user


class CheckRole:
    def __init__(self, allowed_roles: list[Role]):
        self.allowed_roles = allowed_roles

    def __call__(self, user: Annotated[Users, Depends(get_current_user)]) -> Users:
        if user.role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Your role is {user.role.value if hasattr(user.role, 'value') else user.role}. "
                f"Allowed roles: {[role.value for role in self.allowed_roles]}",
            )
        return user


allow_admin = CheckRole([Role.admin])
allow_admin_and_manager = CheckRole([Role.admin, Role.manager])
