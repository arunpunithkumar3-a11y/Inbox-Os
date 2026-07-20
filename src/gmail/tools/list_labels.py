from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from gmail.service import get_gmail_tool


@tool
async def list_labels(config: RunnableConfig = None) -> list:
    """Lists all available Gmail labels in the user's account."""
    configurable = config.get("configurable", {}) if config else {}
    user_id = configurable.get("user_uid")
    if not user_id:
        raise ValueError("User context (user_uid) is missing from the configuration.")

    gmail_tool = await get_gmail_tool(str(user_id))
    return await gmail_tool.list_labels()
