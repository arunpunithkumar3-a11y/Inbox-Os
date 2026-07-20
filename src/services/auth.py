import logging

from sqlalchemy.ext.asyncio.session import AsyncSession
from sqlmodel import select

from src.core.security import create_hash_password
from src.models.auth import UserSignup
from src.models.database import User

logger = logging.getLogger(__name__)


class UserService:
    async def get_user_by_id(self, uid: str, session: AsyncSession):
        import uuid

        try:
            uuid_uid = uuid.UUID(uid) if isinstance(uid, str) else uid
        except ValueError:
            uuid_uid = uid

        stmt = select(User).where(User.uid == uuid_uid)
        result = await session.execute(stmt)
        return result.scalars().first()

    async def get_user_by_email(self, email: str, session: AsyncSession):
        stmt = select(User).where(User.email == email)
        result = await session.execute(stmt)
        return result.scalars().first()

    async def user_exists(self, email: str, session: AsyncSession) -> bool:
        user = await self.get_user_by_email(email, session)
        return user is not None

    async def create_user(self, data: UserSignup, session: AsyncSession):
        user_data = data.model_dump(exclude={"password"})
        new_user = User(**user_data)
        new_user.password_hash = create_hash_password(data.password)
        session.add(new_user)
        await session.commit()
        return new_user

    async def update_user(self, data: UserSignup, user: User, session: AsyncSession):
        for k, v in data.model_dump().items():
            setattr(user, k, v)
        await session.commit()
        return user

    async def delete_user(self, uid: str, session: AsyncSession):
        user = await self.get_user_by_id(uid, session)
        if not user:
            return None
        await session.delete(user)
        await session.commit()
        return user
