import asyncio
from datetime import timedelta
import logging
import httpx
from langchain_mcp_adapters.client import MultiServerMCPClient
from src.config import configure

logger = logging.getLogger(__name__)

def create_mcp_client() -> MultiServerMCPClient:
    return MultiServerMCPClient({
        "gmail_server": {
            "transport": "streamable_http",
            "url": configure.MCP_URL,
            "timeout": timedelta(seconds=120),
        }
    })

async def ping_mcp_server() -> bool:
    url = configure.MCP_URL
    if not url:
        logger.warning("MCP_URL is not configured. Skipping ping.")
        return False

    max_attempts = 15
    logger.info(f"Pinging MCP server at {url} to ensure it is awake...")

    async with httpx.AsyncClient(timeout=10.0) as client:
        for attempt in range(1, max_attempts + 1):
            try:
                response = await client.get(url)
                if response.status_code < 500:
                    logger.info(f"MCP server is online and responded with status {response.status_code} (attempt {attempt}).")
                    return True
                else:
                    logger.warning(
                        f"MCP server returned status {response.status_code} (attempt {attempt}/{max_attempts}). ..."
                    )
            except httpx.HTTPError as e:
                logger.warning(
                    f"Failed to connect to MCP server (attempt {attempt}/{max_attempts}): {e}. ..."
                )
  

    logger.error(f"MCP server at {url} failed to wake up after {max_attempts} attempts.")
    return False
