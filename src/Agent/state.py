from typing import List, Dict, Any, Optional, Literal
from langchain_core.messages import BaseMessage
from typing_extensions import TypedDict, Annotated
from langgraph.graph.message import add_messages
from src.agent.models import planner


class GmailState(TypedDict):
    user_query: str
    messages: Annotated[List[BaseMessage], add_messages]
    plan: Optional[planner]
    confidence_score: float
    initial_route: Optional[Literal["direct", "planner"]]
    summary: str
    error: Dict[str, Any]
    success: bool
    direct_gen_answer: str
