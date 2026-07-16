import logging
from langchain_core.messages import ToolMessage
from langgraph.types import interrupt
from src.agent.state import GmailState

logger = logging.getLogger(__name__)

DANGEROUS_TOOLS = ["send_email", "reply_to_email", "trash_email", "archive_email"]


async def Approval_Agent(state: GmailState):
    last_message = state["messages"][-1]
    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        return {}
    tool_calls = last_message.tool_calls
    dangerous_calls = []
    for tool_call in tool_calls:
        name = tool_call["name"]
        is_dangerous = False
        for dt in DANGEROUS_TOOLS:
            if name == dt or name.endswith("__" + dt) or name.endswith("_" + dt):
                is_dangerous = True
                break
        if is_dangerous:
            dangerous_calls.append(
                {
                    "tool": tool_call["name"],
                    "args": tool_call["args"]
                }
            )
    if not dangerous_calls:
        return {}
    approval = interrupt(
        {
            "type": "tool_approval",
            "tool_calls": dangerous_calls
        }
    )  
    if not approval["approved"]:
        first_tool_call_id = last_message.tool_calls[0]["id"] if last_message.tool_calls else "mock_id"
        return {
            "messages": [
                ToolMessage(
                    content="Execution rejected by user",
                    tool_call_id=first_tool_call_id
                )
            ]
        }
    return {}


def route_after_approval(state: GmailState) -> str:
    last_message = state["messages"][-1]
    if isinstance(last_message, ToolMessage):
        return "ex"
    return "tool"
