import logging
from langchain_core.messages import SystemMessage
from src.agent.state import GmailState
from src.agent.prompts.prompt_loader import get_system_prompt
from src.agent.tools import get_llm
from src.core.database import get_store

logger = logging.getLogger(__name__)


async def direct(state: GmailState, config=None) -> dict:
    """Generate a direct LLM response using conversation history + stored user data."""
    logger.info("Entering direct node...")
    query = state["user_query"]
    stored_data = []

    configurable = config.get("configurable", {}) if config else {}
    user_uid = configurable.get("user_uid")

    if user_uid:
        namespace = ("user", str(user_uid))
        try:
            store = await get_store()
            stored_data = [d.value["data"] for d in await store.asearch(namespace, limit=50)]
        except Exception as exc:
            logger.warning("DB connection failed in direct node: %s", exc)
    else:
        logger.warning("user_uid not found in config inside direct node.")

    logger.info("Direct node fetching from LLM...")
    history_msgs = list(state["messages"])
    summary = state.get("summary")
    if summary:
        history_msgs.append(SystemMessage(content=f"Summary of earlier messages: {summary}"))

    try:
        model = await get_llm()
        prompt_chain = (get_system_prompt() | model).with_retry(stop_after_attempt=3)
        response = await prompt_chain.ainvoke({
            "query": query,
            "history": history_msgs,
            "user_data": stored_data,
            "confidence_score": state.get("confidence_score", 1.0),
        })
        return {
            "messages": [response],
            "direct_gen_answer": response.content,
            "success": True,
        }
    except Exception as exc:
        return {
            "error": {"type": "direct_node", "message": str(exc)},
            "success": False,
        }
