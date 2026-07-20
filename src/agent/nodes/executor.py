import logging
from langchain_core.messages import SystemMessage
from src.agent.state import GmailState
from src.agent.prompts.prompt_loader import get_executor_prompt
from src.agent.tools import get_llm, tools_list

logger = logging.getLogger(__name__)


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
    summary = state.get("summary", "")

    history_msgs = list(state["messages"])
    if summary:
        history_msgs.insert(
            0,
            SystemMessage(content=f"Summary of earlier conversation:\n{summary}"),
        )

    try:
        model = await get_llm()
        llm_with_tools = model.bind_tools(tools_list)
        ex_chain = (get_executor_prompt() | llm_with_tools).with_retry(stop_after_attempt=3)
        response = await ex_chain.ainvoke({
            "query": query,
            "plan": plan,
            "summary": summary if summary else "None",
            "history": history_msgs,
        })
        return {"messages": [response], "success": True}
    except Exception as exc:
        logger.exception("Error in Executor_agent:")
        return {
            "error": {"type": "Executor_agent", "message": str(exc)},
            "success": False,
        }

