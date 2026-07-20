import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager

# Ensure current directory (src) is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.v1.agent import Agent_router
from api.v1.auth import auth_router
from api.v1.gmail import google_router
from core.config import settings
from core.database import close_db

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):

    yield
    from core.redis import redis_client

    await redis_client.close()
    await close_db()


app = FastAPI(
    title="Inbox OS API",
    version="1.0.0",
    lifespan=lifespan,
)

allowed_origins = [
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "https://inbox-os.vercel.app",
]

allowed_origins_env = settings.ALLOWED_ORIGINS
if allowed_origins_env:
    allowed_origins.extend(
        [origin.strip() for origin in allowed_origins_env.split(",") if origin.strip()]
    )
allowed_origins = list(set(allowed_origins))

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["x-thread-id"],
)

app.include_router(auth_router, prefix="/api/auth")
app.include_router(google_router, prefix="/gmail")
app.include_router(Agent_router, prefix="/ai")
