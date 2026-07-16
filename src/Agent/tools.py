import os

from langchain_openai import ChatOpenAI

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

from src.gmail.tools import tools_list

llm_with_tools = llm.bind_tools(tools_list)
formatted_tools_desc = "\n".join([f"- **{t.name}**: {t.description}" for t in tools_list])
tool_names = [t.name for t in tools_list]


