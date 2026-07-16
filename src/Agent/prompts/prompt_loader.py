import os
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

PROMPTS_DIR = os.path.dirname(os.path.abspath(__file__))


def load_prompt_text(filename: str) -> str:
    path = os.path.join(PROMPTS_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def get_planner_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages([
        ("system", load_prompt_text("planner.md")),
        ("human", "query:{query}\navailable tools:{tools}\nconfidence_score:{conf}")
    ])


def get_executor_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages([
        ("system", load_prompt_text("executor.md")),
        MessagesPlaceholder(variable_name="history")
    ])


def get_router_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages([
        ("system", load_prompt_text("router.md")),
        ("human", "Conversation History:\n{messages}\n\nCurrent Query:\n{query}")
    ])


def get_system_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages([
        ("system", load_prompt_text("system.md")),
        ("human", "Query: {query}\n\nUser Data: {user_data}\n\nConversation History: {history}\n\nConfidence Score: {confidence_score}")
    ])


def get_extract_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages([
        ("system", load_prompt_text("extractor.md")),
        ("human", "query: {query}\nexisting_memory: {existing_memory}")
    ])
