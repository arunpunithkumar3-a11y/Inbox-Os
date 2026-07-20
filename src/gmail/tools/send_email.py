from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from gmail.service import get_gmail_tool


@tool
async def send_email(to: str, subject: str, body: str, cc: str = None, bcc: str = None, attachment_path: str = None, config: RunnableConfig = None) -> dict:
    """Sends a new email with optional CC, BCC, and attachment."""
    configurable = config.get("configurable", {}) if config else {}
    user_id = configurable.get("user_uid")
    if not user_id:
        raise ValueError("User context (user_uid) is missing from the configuration.")
        
    gmail_tool = await get_gmail_tool(str(user_id))
    return await gmail_tool.send_email(
        to=to,
        subject=subject,
        body=body,
        cc=cc,
        bcc=bcc,
        attachment_path=attachment_path
    )
