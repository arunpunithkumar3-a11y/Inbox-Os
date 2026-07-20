import logging

from agent.graph import agent_graph
from agent.state import GmailState
from core.database import get_checkpointer

logger = logging.getLogger(__name__)


class GmailAgent:
    def __init__(self, query: str = None, thread_id: str = None, id: str = None):
        self.query = query
        self.thread_id = thread_id
        self.id = id

    async def build_agent(self):
        logger.info("Graph starting...")
        checkpointer = await get_checkpointer()

        graph = await agent_graph(checkpointer=checkpointer, state_schema=GmailState)
        run_config = {
            "configurable": {
                "thread_id": self.thread_id or "",
                "user_uid": self.id,
            }
        }
        return {"graph": graph, "config_material": run_config}

    async def get_chats(self):
        checkpointer = await get_checkpointer()
        graph = await agent_graph(checkpointer=checkpointer, state_schema=GmailState)
        chat_config = {
            "configurable": {
                "thread_id": self.thread_id or "",
                "user_uid": self.id,
            }
        }
        state = await graph.aget_state(config=chat_config)
        return state.values.get("messages", [])
