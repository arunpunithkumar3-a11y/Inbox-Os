import json
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from src.gmail.service import get_gmail_tool


@tool
async def remove_label(message_id: str, label_name: str, config: RunnableConfig = None) -> str:
    """Removes a label from a specific email message using its message ID and label name."""
    configurable = config.get("configurable", {}) if config else {}
    user_id = configurable.get("user_uid")
    if not user_id:
        raise ValueError("User context (user_uid) is missing from the configuration.")

    gmail_tool = await get_gmail_tool(str(user_id))
    res = await gmail_tool.remove_label(message_id=message_id, label_name=label_name)
    return json.dumps(res)
