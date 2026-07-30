import hashlib
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import create_refresh_token
from app.models.refresh_token_model import RefreshToken


class InvalidRefreshTokenError(Exception):
    pass


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class RefreshTokenService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, user_id: int) -> str:
        token = create_refresh_token({"sub": str(user_id)})
        session = RefreshToken(
            user_id=user_id,
            token_hash=hash_refresh_token(token),
            expires_at=self._expires_at(),
        )
        self.db.add(session)
        await self.db.commit()
        return token

    async def rotate(self, current_token: str, user_id: int) -> str:
        session = await self.db.scalar(
            select(RefreshToken)
            .where(RefreshToken.token_hash == hash_refresh_token(current_token))
            .with_for_update()
        )
        if (
            session is None
            or session.user_id != user_id
            or session.expires_at <= datetime.now(UTC)
        ):
            raise InvalidRefreshTokenError

        new_token = create_refresh_token({"sub": str(user_id)})
        session.token_hash = hash_refresh_token(new_token)
        session.expires_at = self._expires_at()
        await self.db.commit()
        return new_token

    async def revoke(self, token: str, user_id: int) -> bool:
        result = await self.db.execute(
            delete(RefreshToken).where(
                RefreshToken.token_hash == hash_refresh_token(token),
                RefreshToken.user_id == user_id,
            )
        )
        await self.db.commit()
        return bool(result.rowcount)

    async def revoke_all(self, user_id: int) -> int:
        result = await self.db.execute(
            delete(RefreshToken).where(RefreshToken.user_id == user_id)
        )
        await self.db.commit()
        return result.rowcount or 0

    @staticmethod
    def _expires_at() -> datetime:
        return datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
