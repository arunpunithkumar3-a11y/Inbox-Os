from typing import Any, Dict, List, Literal, Optional

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import Annotated, TypedDict

from src.agent.models import Planner


class GmailState(TypedDict):
    user_query: str
    messages: Annotated[List[BaseMessage], add_messages]
    plan: Optional[Planner]
    initial_route: Optional[Literal["direct", "planner"]]
    summary: str
    error: Dict[str, Any]
    success: bool
    direct_gen_answer: str
