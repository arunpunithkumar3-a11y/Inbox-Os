import logging
from upstash_redis import Redis
from src.config import configure

logger = logging.getLogger(__name__)

from upstash_redis import Redis

redis_client = Redis(
    url=configure.UPSTASH_REDIS_REST_URL,
    token=configure.UPSTASH_REDIS_REST_TOKEN
)

JTI_EXPIRY = 60 * 60 * 24 * 7  

async def add_jti_to_blacklist(jti: str) -> None:
    """Blacklist a JWT ID so it can no longer be used."""
    try:
        redis_client.set(
            jti,
            "true",
            ex=JTI_EXPIRY
        )
    except Exception as e:
        logger.error(
            f"Failed to add token to blacklist (Redis is unavailable): {e}"
        )


async def token_in_blacklist(jti: str) -> bool:
    """Check whether a JWT ID has been blacklisted."""
    try:
        exists = redis_client.exists(jti)
        return exists == 1
    except Exception as e:
        logger.warning(
            f"Redis is unavailable, skipping blacklist check: {e}"
        )
        return False
    
