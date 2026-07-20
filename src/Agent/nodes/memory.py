import logging
import uuid

from langchain_core.messages import HumanMessage, RemoveMessage

from src.agent.models import extract_data
from src.agent.prompts.prompt_loader import get_extract_prompt
from src.agent.state import GmailState
from src.agent.tools import get_llm
from src.core.database import get_store

logger = logging.getLogger(__name__)


async def memory(state: GmailState, config=None) -> dict:
    """Extract storable user facts from the query and persist them in store."""
    logger.info("Entering memory node...")
    query = state["user_query"]

    configurable = config.get("configurable", {}) if config else {}
    user_uid = configurable.get("user_uid")

    if user_uid:
        namespace = ("user", str(user_uid))
        try:
            store = await get_store()
            stored_data = [
                d.value["data"] for d in await store.asearch(namespace, limit=50)
            ]

            try:
                model = await get_llm()
                extract_chain = (
                    get_extract_prompt()
                    | model.with_structured_output(extract_data, method="json_mode")
                ).with_retry(stop_after_attempt=3)
                response = await extract_chain.ainvoke(
                    {"query": query, "existing_memory": stored_data}
                )
                if response and response.should:
                    if response.memories.is_new and response.memories.content:
                        await store.aput(
                            namespace,
                            str(uuid.uuid4()),
                            {"data": response.memories.content},
                        )
            except Exception as exc:
                logger.error(
                    "Memory node extraction failed (gracefully bypassed): %s", exc
                )
        except Exception as exc:
            logger.warning(
                "Memory node DB access failed (gracefully bypassed): %s", exc
            )
    else:
        logger.warning("user_uid not found in config inside memory node.")

    result = {"plan": None}

    if len(state["messages"]) > 15:
        existing_summary = state.get("summary", "")
        if existing_summary:
            prompt = (
                f"Existing summary:\n{existing_summary}\n\n"
                "Extend the summary using the new conversation above."
            )
        else:
            prompt = "Summarize the above conversation."

        messages_for_summary = state["messages"] + [HumanMessage(content=prompt)]
        model = await get_llm()
        response = await model.ainvoke(messages_for_summary)

        messages_to_delete = state["messages"][:-2]

        result["summary"] = response.content
        result["messages"] = [RemoveMessage(id=m.id) for m in messages_to_delete]

    return result
