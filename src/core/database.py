import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.postgres import AsyncPostgresStore
from src.config import configure

logger = logging.getLogger(__name__)

engine = create_async_engine(
    configure.DATABASE_URL,
    echo=False,
    pool_size=10,
    max_overflow=20,
    pool_recycle=1800,
    pool_pre_ping=True,
)

async_session_factory = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

async def init_db():
    from sqlmodel import SQLModel
    from src.models.database import User, GoogleAccount, OAuthSession, ChatState
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    logger.info("Database tables initialised.")

async def get_session():
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise

_PG_URL = configure.DATABASE_URL.replace("+asyncpg", "")

_pool: AsyncConnectionPool | None = None
_checkpointer: AsyncPostgresSaver | None = None
_store: AsyncPostgresStore | None = None

async def _get_pool() -> AsyncConnectionPool:
    global _pool
    if _pool is None:
        _pool = AsyncConnectionPool(
            conninfo=_PG_URL,
            min_size=1,
            max_size=10,
            open=False,
            kwargs={"autocommit": True},
        )
        await _pool.open()
        logger.info("LangGraph connection pool opened.")
    return _pool

async def get_checkpointer() -> AsyncPostgresSaver:
    global _checkpointer
    if _checkpointer is None:
        _checkpointer = AsyncPostgresSaver(await _get_pool())
        await _checkpointer.setup()
        logger.info("Checkpointer ready.")
    return _checkpointer

async def get_store() -> AsyncPostgresStore:
    global _store
    if _store is None:
        _store = AsyncPostgresStore(await _get_pool())
        await _store.setup()
        logger.info("Store ready.")
    return _store

async def close_db():
    global _pool, _checkpointer, _store
    if _pool:
        await _pool.close()
        _pool = _checkpointer = _store = None
        logger.info("LangGraph pool closed.")
    await engine.dispose()
    logger.info("SQLAlchemy engine disposed.")
