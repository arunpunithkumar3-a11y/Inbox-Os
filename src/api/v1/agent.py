import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.types import Command
from sqlalchemy.ext.asyncio.session import AsyncSession

from src.agent.tools import build_agent_instance, build_thread
from src.core.database import get_session
from src.core.security import verify_token
from src.models.agent import AgentEndpointRequest, ResumeRequest
from src.services.agent import AgentService
from src.agent.agent import GmailAgent

logger = logging.getLogger(__name__)

Agent_router = APIRouter()
agent_serv = AgentService()


@Agent_router.post("/agent", status_code=status.HTTP_200_OK)
async def Agent_endpoint(
    req: AgentEndpointRequest,
    session: AsyncSession = Depends(get_session),
    token_details=Depends(verify_token),
):
    user_id = token_details["user_data"]["user_id"]
    data = req.data

    if not data.thread_id:
        thread_id = str(uuid.uuid4())
        await build_thread(
            user_id=user_id,
            thread_id=thread_id,
            query=data.query,
            session=session,
        )

    else:
        thread_id = data.thread_id

    agent_instance = await build_agent_instance(
        user_id=user_id, thread_id=thread_id, query=data.query
    )

    graph = agent_instance["graph"]
    run_config = agent_instance["config"]

    async def event_gen():
        try:
            async for event in graph.astream_events(
                {
                    "user_query": data.query,
                    "messages": [HumanMessage(content=data.query)],
                    "initial_route": None,
                    "plan": None,
                    "summary": "",
                    "error": {},
                    "success": False,
                    "direct_gen_answer": "",
                },
                config=run_config,
                version="v2",
            ):
                event_type = event["event"]

                if event_type == "on_chat_model_stream" and event["metadata"].get(
                    "langgraph_node"
                ) in ("direct", "ex"):
                    chunk = event["data"]["chunk"]
                    if chunk.content:
                        yield f"data: {
                            json.dumps({'type': 'token', 'content': chunk.content})
                        }\n\n"

        except Exception as exc:
            logger.exception("Error in SSE event generation: %s", exc)
            yield f"data: {
                json.dumps(
                    {
                        'type': 'error',
                        'content': f'An unexpected error occurred during execution: {str(exc)}',
                    }
                )
            }\n\n"
            return

        # Fetch the state only once at the end
        snapshot = await graph.aget_state(run_config)
        if snapshot.interrupts:
            interrupt_val = snapshot.interrupts[0].value
            yield f"data: {
                json.dumps({'type': 'interrupt', 'value': interrupt_val})
            }\n\n"
        else:
            messages = snapshot.values.get("messages", [])
            final_output = messages[-1].content if messages else ""
            yield f"data: {
                json.dumps({'type': 'done', 'output': str(final_output)})
            }\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "x-thread-id": thread_id,
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@Agent_router.post("/resume", status_code=status.HTTP_200_OK)
async def Resume_endpoint(
    data: ResumeRequest,
    session: AsyncSession = Depends(get_session),
    token_details=Depends(verify_token),
):
    user_id = token_details["user_data"]["user_id"]

    agent_instance = await build_agent_instance(
        user_id=user_id, thread_id=data.thread_id, query="resume"
    )

    graph = agent_instance["graph"]
    run_config = agent_instance["config"]

    async def event_gen():
        try:
            async for event in graph.astream_events(
                Command(resume=data.resume_data), config=run_config, version="v2"
            ):
                event_type = event["event"]

                if event_type == "on_chat_model_stream" and event["metadata"].get(
                    "langgraph_node"
                ) in ("direct", "ex"):
                    chunk = event["data"]["chunk"]
                    if chunk.content:
                        yield f"data: {
                            json.dumps({'type': 'token', 'content': chunk.content})
                        }\n\n"

        except Exception as exc:
            logger.exception("Error in SSE event generation (resume): %s", exc)
            yield f"data: {
                json.dumps(
                    {
                        'type': 'error',
                        'content': f'An unexpected error occurred during execution: {str(exc)}',
                    }
                )
            }\n\n"
            return

        # Fetch the state only once at the end
        snapshot = await graph.aget_state(run_config)
        if snapshot.interrupts:
            interrupt_val = snapshot.interrupts[0].value
            yield f"data: {
                json.dumps({'type': 'interrupt', 'value': interrupt_val})
            }\n\n"
        else:
            messages = snapshot.values.get("messages", [])
            final_output = messages[-1].content if messages else ""
            yield f"data: {
                json.dumps({'type': 'done', 'output': str(final_output)})
            }\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "x-thread-id": data.thread_id,
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@Agent_router.get("/thread", status_code=status.HTTP_200_OK)
async def get_chat_threads(
    session: AsyncSession = Depends(get_session),
    token_details=Depends(verify_token),
):
    user_id = token_details["user_data"]["user_id"]
    threads = await agent_serv.get_thread_by_id(uid=user_id, session=session)
    return threads


@Agent_router.delete("/thread/{thread_id}", status_code=status.HTTP_200_OK)
async def delete_chat_thread(
    thread_id: str,
    session: AsyncSession = Depends(get_session),
    token_details=Depends(verify_token),
):
    user_id = token_details["user_data"]["user_id"]
    success = await agent_serv.delete_thread_by_id(
        thread_id=thread_id, uid=user_id, session=session
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "Thread not found or unauthorized"},
        )
    return {"message": "Thread deleted successfully"}


@Agent_router.get("/chats/{thread_id}", status_code=status.HTTP_200_OK)
async def get_chats(
    thread_id: str,
    session: AsyncSession = Depends(get_session),
    token_details=Depends(verify_token),
):
    user_id = token_details["user_data"]["user_id"]

    agent = GmailAgent(thread_id=thread_id, id=user_id)
    try:
        chats = await agent.get_chats()
        temp_msg = []
        for msg in chats:
            if isinstance(msg, ToolMessage):
                continue

            if isinstance(msg, AIMessage):
                if msg.tool_calls and not msg.content:
                    continue
                content = (
                    msg.content if isinstance(msg.content, str) else str(msg.content)
                )
                if content.strip():
                    temp_msg.append({"role": "agent", "content": content})
                continue
            if isinstance(msg, HumanMessage):
                temp_msg.append({"role": "user", "content": msg.content})
        return temp_msg

    except Exception as exc:
        logger.exception("Error fetching chats: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "Failed to fetch chats. Try again later."},
        )
