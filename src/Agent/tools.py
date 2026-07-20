import logging

from fastapi import Depends
from langchain_openai import ChatOpenAI
from sqlalchemy.ext.asyncio.session import AsyncSession

from src.core.config import settings
from src.core.database import get_session
from src.gmail.tools import tools_list
from src.services.agent import AgentService

agent_service = AgentService()
logger = logging.getLogger(__name__)
llm = ChatOpenAI(
    base_url=settings.MODEL_BASE_URL,
    model=settings.GROQ_AI_MODEL,
    api_key=settings.GROQ_API_KEY,
)


async def get_llm():
    return llm


llm_with_tools = llm.bind_tools(tools_list)


async def build_agent_instance(
    user_id: str,
    thread_id: str,
    query: str,
):
    from src.agent.agent import GmailAgent

    agent = GmailAgent(query=query, thread_id=thread_id, id=user_id)
    agent_data = await agent.build_agent()
    return {"graph": agent_data["graph"], "config": agent_data["config_material"]}


async def build_thread(
    user_id: str,
    thread_id: str,
    query: str,
    session: AsyncSession = Depends(get_session),
) -> None:
    prompt = f"""
Generate a short chat title.

Rules:
- Max 4 words
- No punctuation
- Professional
- Concise

Message:
{query}
"""
    try:
        model = await get_llm()
        response = await model.ainvoke(prompt)
        chat_title = response.content.strip()
        if not chat_title:
            chat_title = "New Conversation"
    except Exception as exc:
        logger.warning("Failed to generate chat title using LLM: %s", exc)
        chat_title = "New Conversation"

    thread_data = {
        "user_uid": user_id,
        "thread_id": thread_id,
        "chat_title": chat_title,
    }

    await agent_service.create_thread_id(data=thread_data, session=session)
