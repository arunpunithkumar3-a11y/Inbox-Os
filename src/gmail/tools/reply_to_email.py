import json
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from src.gmail.service import get_gmail_tool


@tool
async def reply_to_email(message_id: str, reply_body: str, config: RunnableConfig = None) -> str:
    """Reply to an existing email conversation thread using its message ID."""
    configurable = config.get("configurable", {}) if config else {}
    user_id = configurable.get("user_uid")
    if not user_id:
        raise ValueError("User context (user_uid) is missing from the configuration.")
        
    gmail_tool = await get_gmail_tool(str(user_id))
    res = await gmail_tool.reply_to_email(
        message_id=message_id,
        reply_body=reply_body
    )
    return json.dumps(res)
