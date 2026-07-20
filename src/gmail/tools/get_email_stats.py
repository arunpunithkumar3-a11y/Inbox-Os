from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from gmail.service import get_gmail_tool


@tool
async def get_email_stats(config: RunnableConfig = None) -> dict:
    """Provides mailbox overview metrics and message counts."""
    configurable = config.get("configurable", {}) if config else {}
    user_id = configurable.get("user_uid")
    if not user_id:
        raise ValueError("User context (user_uid) is missing from the configuration.")

    gmail_tool = await get_gmail_tool(str(user_id))
    return await gmail_tool.get_email_stats()
