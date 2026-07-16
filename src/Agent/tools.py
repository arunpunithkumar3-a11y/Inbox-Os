import os
from langchain_core.tools import StructuredTool
from langchain_openai import ChatOpenAI
from src.Agent.utils import create_mcp_client
from src.config import configure


_api_key = configure.OPENROUTER_API_KEY or os.getenv("OPENROUTER_API_KEY", "")

llm = ChatOpenAI(
    model=configure.OPEN_AI_MODEL,
    base_url=configure.BASE_URL,
    api_key=_api_key,      
    streaming=True,
)

llm1 = ChatOpenAI(
    model=configure.LIQUID_MODEL,
    base_url=configure.BASE_URL,
    api_key=_api_key,
)

class AgentTools:
    def __init__(self, user_data):
        self.user_data = user_data
        self.mcp_client = create_mcp_client()

    async def inject_user_data(self) -> list:
        from src.Agent.utils import ping_mcp_server
        await ping_mcp_server()

        tools = await self.mcp_client.get_tools()
        for tool in tools:
            original_coroutine = tool.coroutine

            def make_patched(fn):
                async def patched(*args, **kwargs):
                    kwargs["user_data"] = self.user_data
                    return await fn(*args, **kwargs)
                return patched

            tool.coroutine = make_patched(original_coroutine)

        return tools
