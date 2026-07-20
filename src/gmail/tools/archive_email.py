from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from src.gmail.service import get_gmail_tool


@tool
async def archive_email(message_id: str, config: RunnableConfig = None) -> str:
    """Archive a specific email using its message ID."""
    configurable = config.get("configurable", {}) if config else {}
    user_id = configurable.get("user_uid")
    if not user_id:
        raise ValueError("User context (user_uid) is missing from the configuration.")
        
    gmail_tool = await get_gmail_tool(str(user_id))
    await gmail_tool.archive_email(message_id=message_id)
    return f"Email {message_id} successfully archived."
