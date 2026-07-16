import logging
from src.agent.state import GmailState
from src.agent.prompts import get_planner_prompt
from src.agent.models import planner
from src.agent.tools import llm, formatted_tools_desc

logger = logging.getLogger(__name__)

planner_chain = (get_planner_prompt() | llm.with_structured_output(planner, method="json_mode")).with_retry(stop_after_attempt=3)


async def Planner_Agent(state: GmailState) -> dict:
    logger.info("Entering Planner_Agent node...")
    query = state["user_query"]
    if state.get("initial_route") != "planner":
        return {}

    try:
        result = await planner_chain.ainvoke({
            "query": query,
            "tools": formatted_tools_desc,
            "conf": state["confidence_score"],
        })
        return {"plan": result, "success": True}
    except Exception as exc:
        return {
            "error": {"type": "Planner_Agent", "message": str(exc)},
            "success": False,
        }
