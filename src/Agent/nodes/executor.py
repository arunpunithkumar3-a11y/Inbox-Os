import logging
from src.agent.state import GmailState
from src.agent.prompts import get_executor_prompt
from src.agent.tools import llm_with_tools, formatted_tools_desc

logger = logging.getLogger(__name__)

ex_chain = (get_executor_prompt() | llm_with_tools).with_retry(stop_after_attempt=3)


async def Executor_agent(state: GmailState) -> dict:
    logger.info("Entering Executor_agent node...")
    if state.get("initial_route") != "planner":
        return {}

    if state.get("error"):
        return {}

    plan = state.get("plan")
    if not plan:
        return {
            "error": {"type": "Executor_agent", "message": "no plan available"},
            "success": False,
        }

    query = state["user_query"]

    try:
        response = await ex_chain.ainvoke({
            "query": query,
            "plan": plan,
            "history": state["messages"],
            "av": formatted_tools_desc,
        })
        return {"messages": [response], "success": True}
    except Exception as exc:
        return {
            "error": {"type": "Executor_agent", "message": str(exc)},
            "success": False,
        }
