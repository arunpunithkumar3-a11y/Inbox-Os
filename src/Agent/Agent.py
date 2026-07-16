import logging

from src.Agent.Agent_Graph import agent_graph
from src.Agent.Agent_States import GmailState
from src.Agent.Agent_functions import GmailAgentNodes
from src.Agent.tools import AgentTools
from src.config import configure
from src.db.main import get_checkpointer

logger = logging.getLogger(__name__)


class GmailAgent:
    def __init__(self, query: str = None, thread_id: str = None, id: str = None, p_data: dict = None):
        self.query = query
        self.thread_id = thread_id
        self.id = id
        self.p_data = p_data

    async def build_agent(self):
        logger.info("Graph starting...")
        agent_tools = AgentTools(user_data=self.p_data)
        tools_list = await agent_tools.inject_user_data()
        nodes = GmailAgentNodes(user_uid=self.id, p_data=self.p_data, tools_list=tools_list)
        checkpointer = await get_checkpointer()

        graph = await agent_graph(nodes=nodes, tools_list=tools_list, checkpointer=checkpointer, state_schema=GmailState)
        run_config = {
            "configurable": {
                "thread_id": self.thread_id or "",
            }
        }
        return {
            "graph": graph,
            "config_material": run_config
        }

    async def get_chats(self):
        agent_tools = AgentTools(user_data=self.p_data)
        tools_list = await agent_tools.inject_user_data()
        nodes = GmailAgentNodes(user_uid=self.id, p_data=self.p_data, tools_list=tools_list)
        checkpointer = await get_checkpointer()
        graph = await agent_graph(nodes=nodes, tools_list=tools_list, checkpointer=checkpointer, state_schema=GmailState)
        chat_config = {
            "configurable": {
                "thread_id": self.thread_id or "",
            }
        }
        state = await graph.aget_state(config=chat_config)
        return state.values.get("messages", [])
