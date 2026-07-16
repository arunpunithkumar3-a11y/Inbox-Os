import logging
import uuid
import asyncio

from src.Agent.Agent_States import GmailState
from src.Agent.prompts import (
    planner_prompt, ex_prompt, router_prompt,
    system_prompt, Extract_Prompt
)
from langchain_core.messages import ToolMessage, SystemMessage, HumanMessage,AIMessage
from src.Agent.tools import AgentTools, llm
from src.Agent.models import planner, router, extract_data
from langgraph.graph.message import RemoveMessage
from src.db.main import get_store
from langgraph.types import interrupt


logger = logging.getLogger(__name__)
DANGEROUS_TOOLS = ["send_email", "reply_to_email", "trash_email", "archive_email"]

class GmailAgentNodes:
    def __init__(self, user_uid, p_data, tools_list):
        """
        Accept pre-built tools_list so we never call asyncio.run() inside
        an already-running event loop.
        """
        self.user_uid = user_uid
        self.p_data = p_data
        self.namespace = ("user", self.user_uid)
        self.tools_list = tools_list
        self.llm_with_tools = llm.bind_tools(self.tools_list)
        self.formatted_tools_desc = "\n".join([
            f"- **{t.name}**: {t.description}" for t in self.tools_list
        ])
        self.tool_names = [t.name for t in self.tools_list]

        self.planner_chain = (planner_prompt | llm.with_structured_output(planner, method="json_mode")).with_retry(stop_after_attempt=3)
        self.router_chain = (router_prompt | llm.with_structured_output(router, method="json_mode")).with_retry(stop_after_attempt=3)
        self.prompt_chain = (system_prompt | llm).with_retry(stop_after_attempt=3)
        self.extract_chain = (Extract_Prompt | llm.with_structured_output(extract_data, method="json_mode")).with_retry(stop_after_attempt=3)
        self.ex_chain = (ex_prompt | self.llm_with_tools).with_retry(stop_after_attempt=3)

    async def Planner_Agent(self, state: GmailState) -> dict:
        logger.info("Entering Planner_Agent node...")
        query = state["user_query"]
        if state.get("initial_route") != "planner":
            return {}

       
        try:
                result = await self.planner_chain.ainvoke({
                    "query": query,
                    "tools": self.formatted_tools_desc,
                    "conf": state["confidence_score"],
                })
                return {"plan": result, "success": True}
        except Exception as exc:
                return {
                    "error": {"type": "Planner_Agent", "message": str(exc)},
                    "success": False,
                }

    async def Executor_agent(self, state: GmailState) -> dict:
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
            response = await self.ex_chain.ainvoke({
                "query": query,
                "plan": plan,
                "history": state["messages"],
                "av": self.formatted_tools_desc,
            })
            return {"messages": [response], "success": True}
        except Exception as exc:
            return {
                "error": {"type": "Executor_agent", "message": str(exc)},
                "success": False,
            }

    async def router(self, state: GmailState) -> dict:
        """Classify the user query and decide which pipeline to activate."""
        logger.info("Entering router node...")
        query = state["user_query"]

        try:
            response = await self.router_chain.ainvoke({
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

    def decide(self, state: GmailState) -> str:
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

    async def direct(self, state: GmailState) -> dict:
        """Generate a direct LLM response using conversation history + stored user data."""
        logger.info("Entering direct node...")
        query = state["user_query"]
        stored_data = []
        try:
            store = await get_store()
            stored_data = [d.value["data"] for d in await store.asearch(self.namespace, limit=50)]
        except Exception as exc:
            logger.warning("DB connection failed in direct node: %s", exc)

        logger.info("Direct node fetching from LLM...")
        history_msgs = list(state["messages"])
        summary = state.get("summary")
        if summary:
            history_msgs.append(SystemMessage(content=f"Summary of earlier messages: {summary}"))

        try:
            response = await self.prompt_chain.ainvoke({
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

    async def memory(self, state: GmailState) -> dict:
        """Extract storable user facts from the query and persist them in store."""
        logger.info("Entering memory node...")
        query = state["user_query"]
        try:
            store = await get_store()
            stored_data = [d.value["data"] for d in await store.asearch(self.namespace, limit=50)]
        
            try:
                response = await self.extract_chain.ainvoke({"query": query, "existing_memory": stored_data})
                if response and response.should:
                    if response.memories.is_new and response.memories.content:
                        await store.aput(self.namespace, str(uuid.uuid4()), {"data": response.memories.content})
            except Exception as exc:
                logger.error("Memory node extraction failed (gracefully bypassed): %s", exc)
        except Exception as exc:
            logger.warning("Memory node DB access failed (gracefully bypassed): %s", exc)


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
            response = await llm.ainvoke(messages_for_summary)

            messages_to_delete = state["messages"][:-2]


            result["summary"] = response.content
            result["messages"] = [RemoveMessage(id=m.id) for m in messages_to_delete]

        return result

    async def Validator_Agent(self, state: GmailState):
        conf_score = state["confidence_score"]
        if state["initial_route"] in ["direct","planner"]:
            conf_score +=0.2
        else:
            conf_score-=0.3
        if state["initial_route"] =="planner" and  state["plan"]:
            conf_score+=0.2
        else:
            conf_score-=0.2
        messages = state.get("messages",[])
        if messages:
            last_message = messages[-1]
            if isinstance(last_message,AIMessage):
                response = last_message.content
                if response:
                    conf_score+=0.2
                else:
                    conf_score-=0.2
                if "tool_calls" in response:
                    conf_score-=0.4
            else:
                conf_score-=0.2
        else:
            conf_score-=0.4
        if state.get("error"):
            conf_score-=0.5
        else:
            conf_score+=0.1
        if state.get("success"):
            conf_score+=0.2

        conf_score = max(0.0,min(conf_score,1))                           
        return {"confidence_score": conf_score}


    async def Approval_Agent(self,state:GmailState):
        last_message = state["messages"][-1]
        tool_calls = last_message.tool_calls
        dangerous_calls = []
        for tool_call in tool_calls:
            name = tool_call["name"]
            is_dangerous = False
            for dt in DANGEROUS_TOOLS:
                if name == dt or name.endswith("__" + dt) or name.endswith("_" + dt):
                    is_dangerous = True
                    break
            if is_dangerous:
                dangerous_calls.append(
                    {
                        "tool":tool_call["name"],
                        "args":tool_call["args"]
                    }
                )
        if not dangerous_calls:
            return {}
        approval = interrupt(
            {
                "type":"tool_approval",
                "tool_calls":dangerous_calls
            }
        )  
        if not approval["approved"]:
            first_tool_call_id = last_message.tool_calls[0]["id"] if last_message.tool_calls else "mock_id"
            return {
                "messages": [
                    ToolMessage(
                        content="Execution rejected by user",
                        tool_call_id=first_tool_call_id
                    )
                ]
            }
        return {}     
    def route_after_approval(self, state: GmailState) -> str:

        last_message = state["messages"][-1]
        if isinstance(last_message, ToolMessage):
           return "ex"
        return "tool"