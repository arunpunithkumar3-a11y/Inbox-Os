import json
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from src.gmail.service import get_gmail_tool


@tool
async def create_draft(
    to: str,
    subject: str,
    body: str,
    cc: str = None,
    bcc: str = None,
    attachment_path: str = None,
    config: RunnableConfig = None,
) -> str:
    """Creates a draft email with optional CC, BCC, and attachment."""
    configurable = config.get("configurable", {}) if config else {}
    user_id = configurable.get("user_uid")
    if not user_id:
        raise ValueError("User context (user_uid) is missing from the configuration.")

    gmail_tool = await get_gmail_tool(str(user_id))
    res = await gmail_tool.create_draft(
        to=to,
        subject=subject,
        body=body,
        cc=cc,
        bcc=bcc,
        attachment_path=attachment_path,
    )
    return json.dumps(res)
