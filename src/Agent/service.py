import logging

from src.db.model import ChatState
from sqlmodel import select
from sqlalchemy.ext.asyncio.session import AsyncSession




class AgentService:
    async def create_thread_id(self, data: dict, session: AsyncSession):
        new_thread = ChatState(**data)
        session.add(new_thread)
        await session.commit()
        return new_thread

    async def get_thread_by_id(self, uid: str, session: AsyncSession):
        stmt = select(ChatState).where(ChatState.user_uid == uid).order_by(ChatState.created_at.desc())
        result = await session.execute(stmt)
        return result.scalars().all()

    async def delete_thread_by_id(self, thread_id: str, uid: str, session: AsyncSession):
        stmt = select(ChatState).where(ChatState.thread_id == thread_id, ChatState.user_uid == uid)
        result = await session.execute(stmt)
        thread = result.scalars().first()
        if thread:
            await session.delete(thread)
            await session.commit()
            return True
        return False
