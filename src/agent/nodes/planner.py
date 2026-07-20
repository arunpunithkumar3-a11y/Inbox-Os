import logging
from src.agent.state import GmailState
from src.agent.prompts.prompt_loader import get_planner_prompt
from src.agent.models import Planner
from src.agent.tools import get_llm

logger = logging.getLogger(__name__)


async def Planner_Agent(state: GmailState) -> dict:
    logger.info("Entering Planner_Agent node...")
    query = state["user_query"]
    if state.get("initial_route") != "planner":
        return {}

    try:
        model = await get_llm()
        planner_chain = (get_planner_prompt() | model.with_structured_output(Planner, method="json_mode")).with_retry(stop_after_attempt=3)
        result = await planner_chain.ainvoke({
            "query": query,
        })
        return {"plan": result, "success": True}
    except Exception as exc:
        logger.exception("Error in Planner_Agent:")
        return {
            "error": {"type": "Planner_Agent", "message": str(exc)},
            "success": False,
        }
