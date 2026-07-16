import logging
from src.agent.state import GmailState
from src.agent.prompts import get_router_prompt
from src.agent.models import router as router_model
from src.agent.tools import llm

logger = logging.getLogger(__name__)

router_chain = (get_router_prompt() | llm.with_structured_output(router_model, method="json_mode")).with_retry(stop_after_attempt=3)


async def router(state: GmailState) -> dict:
    """Classify the user query and decide which pipeline to activate."""
    logger.info("Entering router node...")
    query = state["user_query"]

    try:
        response = await router_chain.ainvoke({
            "query": query,
            "messages": state["messages"],
        })
        logger.info("Router finished — route=%s", response.initial_route)
        return {
            "initial_route": response.initial_route,
            "success": True,
        }
    except Exception as exc:
        return {
            "error": {"type": "router_node", "message": str(exc)},
            "success": False,
        }


def decide(state: GmailState) -> str:
    """
    Conditional edge after the router node.
    Falls back to 'direct' on error so the agent
    always gives a response rather than silently failing.
    """
    if state.get("error"):
        return "direct"

    initial_route = state.get("initial_route")
    if initial_route == "direct":
        return "direct"
    return "planner"
