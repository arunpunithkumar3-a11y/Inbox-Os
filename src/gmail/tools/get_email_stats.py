import json
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from src.gmail.service import get_gmail_tool


@tool
async def get_email_stats(config: RunnableConfig = None) -> str:
    """Provides mailbox overview metrics and message counts."""
    configurable = config.get("configurable", {}) if config else {}
    user_id = configurable.get("user_uid")
    if not user_id:
        raise ValueError("User context (user_uid) is missing from the configuration.")

    gmail_tool = await get_gmail_tool(str(user_id))
    res = await gmail_tool.get_email_stats()
    return json.dumps(res)
