import logging
import uuid
import json
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio.session import AsyncSession
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from src.agent.tools import llm1
from src.agent.agent import GmailAgent
from src.services.agent import AgentService
from src.models.agent import AgentRequest, ResumeRequest
from langgraph.types import Command
from langgraph.errors import GraphInterrupt
from src.core.security import verify_token
from src.core.database import get_session

logger = logging.getLogger(__name__)

Agent_router = APIRouter()
agent_serv = AgentService()


async def build_agent_instance(
    user_id: str,
    thread_id: str,
    query: str,
    session: AsyncSession,
):
    agent = GmailAgent(
        query=query,
        thread_id=thread_id,
        id=user_id
    )

    agent_data = await agent.build_agent()

    return {
        "graph": agent_data["graph"],
        "config": agent_data["config_material"]
    }


@Agent_router.post("/agent", status_code=status.HTTP_200_OK)
async def Agent_endpoint(
    data: AgentRequest,
    state: Optional[dict] = None,
    session: AsyncSession = Depends(get_session),
    token_details=Depends(verify_token),
):
    user_id = token_details["user_data"]["user_id"]

    if not data.thread_id:
        thread_id = str(uuid.uuid4())
        prompt = f"""
Generate a short chat title.

Rules:
- Max 4 words
- No punctuation
- Professional
- Concise

Message:
{data.query}
"""
        try:
            response = await llm1.ainvoke(prompt)
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

        await agent_serv.create_thread_id(
            data=thread_data,
            session=session
        )

    else:
        thread_id = data.thread_id

    agent_instance = await build_agent_instance(
        user_id=user_id,
        thread_id=thread_id,
        query=data.query,
        session=session
    )

    graph = agent_instance["graph"]
    run_config = agent_instance["config"]

    async def event_gen():
        try:
            async for event in graph.astream_events(
                {
                    "messages": [
                        HumanMessage(content=data.query)
                    ],
                    "user_query": data.query,
                    "confidence_score": state.get("confidence_score", 1.0) if state else 1.0,
                    "initial_route": None,
                    "plan": None,
                    "summary": "",
                    "error": {},
                    "success": False,
                    "direct_gen_answer": "",
                },
                config=run_config,
                version="v2"
            ):
                event_type = event["event"]

                if event_type == "on_chat_model_stream" and event["metadata"].get("langgraph_node") in ("direct", "ex"):
                    chunk = event["data"]["chunk"]
                    if chunk.content:
                        yield f"data: {json.dumps({
                            'type': 'token',
                            'content': chunk.content
                        })}\n\n"

                elif event_type == "on_tool_start":
                    yield f"data: {json.dumps({
                        'type': 'tool_start',
                        'tool': event['name'],
                        'input': event['data'].get('input')
                    })}\n\n"

                elif event_type == "on_tool_end":
                    yield f"data: {json.dumps({
                        'type': 'tool_end',
                        'tool': event['name'],
                        'output': str(event['data'].get('output'))
                    })}\n\n"

                elif event_type == "on_node_start":
                    node_name = event.get("metadata", {}).get("langgraph_node")
                    if node_name:
                        yield f"data: {json.dumps({
                            'type': 'node_start',
                            'node': node_name
                        })}\n\n"

                elif event_type == "on_chain_end":
                    output = event["data"].get("output")
                    if not output:
                        continue

                    yield f"data: {json.dumps({
                        'type': 'done',
                        'output': str(output)
                    })}\n\n"

            snapshot = await graph.aget_state(run_config)
            if snapshot.interrupts:
                interrupt_val = snapshot.interrupts[0].value
                yield f"data: {json.dumps({
                    'type': 'interrupt',
                    'value': interrupt_val
                })}\n\n"

        except GraphInterrupt:
            snapshot = await graph.aget_state(run_config)
            if snapshot.interrupts:
                interrupt_val = snapshot.interrupts[0].value
                yield f"data: {json.dumps({
                    'type': 'interrupt',
                    'value': interrupt_val
                })}\n\n"
            return
        except Exception as exc:
            logger.exception("Error in SSE event generation: %s", exc)
            yield f"data: {json.dumps({
                'type': 'error',
                'content': f'An unexpected error occurred during execution: {str(exc)}'
            })}\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "x-thread-id": thread_id,
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@Agent_router.post("/resume", status_code=status.HTTP_200_OK)
async def Resume_endpoint(
    data: ResumeRequest,
    session: AsyncSession = Depends(get_session),
    token_details=Depends(verify_token),
):
    user_id = token_details["user_data"]["user_id"]

    agent_instance = await build_agent_instance(
        user_id=user_id,
        thread_id=data.thread_id,
        query="resume",
        session=session
    )

    graph = agent_instance["graph"]
    run_config = agent_instance["config"]

    async def event_gen():
        try:
            async for event in graph.astream_events(
                Command(
                    resume=data.resume_data
                ),
                config=run_config,
                version="v2"
            ):
                event_type = event["event"]

                if event_type == "on_chat_model_stream":
                    chunk = event["data"]["chunk"]
                    if chunk.content:
                        yield f"data: {json.dumps({
                            'type': 'token',
                            'content': chunk.content
                        })}\n\n"

                elif event_type == "on_chain_end":
                    output = event["data"].get("output")
                    if not output:
                        continue

                    yield f"data: {json.dumps({
                        'type': 'done',
                        'output': str(output)
                    })}\n\n"

            snapshot = await graph.aget_state(run_config)
            if snapshot.interrupts:
                interrupt_val = snapshot.interrupts[0].value
                yield f"data: {json.dumps({
                    'type': 'interrupt',
                    'value': interrupt_val
                })}\n\n"

        except GraphInterrupt:
            snapshot = await graph.aget_state(run_config)
            if snapshot.interrupts:
                interrupt_val = snapshot.interrupts[0].value
                yield f"data: {json.dumps({
                    'type': 'interrupt',
                    'value': interrupt_val
                })}\n\n"
            return
        except Exception as exc:
            logger.exception("Error in SSE event generation (resume): %s", exc)
            yield f"data: {json.dumps({
                'type': 'error',
                'content': f'An unexpected error occurred during execution: {str(exc)}'
            })}\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "x-thread-id": data.thread_id,
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
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
                content = msg.content if isinstance(msg.content, str) else str(msg.content)
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
