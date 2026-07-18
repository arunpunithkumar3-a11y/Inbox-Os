from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from src.gmail.service import get_gmail_tool


@tool
async def read_emails(query: str = "", max_results: int = 5, config: RunnableConfig = None) -> list:
    """Fetch emails using search queries.
    
    query examples:
      'is:unread'           → unread emails
      'from:someone@x.com'  → from specific sender
      'subject:invoice'     → by subject
      'is:unread label:inbox' → unread inbox
    """
    configurable = config.get("configurable", {}) if config else {}
    user_id = configurable.get("user_uid")
    if not user_id:
        raise ValueError("User context (user_uid) is missing from the configuration.")
        
    gmail_tool = await get_gmail_tool(str(user_id))
    return await gmail_tool.read_emails(max_results=max_results, query=query)
