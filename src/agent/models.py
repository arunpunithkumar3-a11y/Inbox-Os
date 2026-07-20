from pydantic import BaseModel, Field
from typing import List, Literal, Optional


class Planner(BaseModel):
    tool_to_use: List[str] = Field(
        description="Ordered list of tools that should be executed."
    )

    execution_context: str = Field(
        description="Clear execution instructions for the executor, including search queries, parameters, email content, and any important context required to execute the tools."
    )

    reasoning: str = Field(
        description="A brief explanation of why this execution plan was chosen."
    )


class ExtractItem(BaseModel):
    content: str = Field(description="Extracted information or empty string", default="")
    is_new: bool = Field(description="True if this memory is NEW and should be stored. False if duplicate/already known.")


class extract_data(BaseModel):
    memories: ExtractItem = Field(description="Atomic user memories to store")
    should: bool = Field(description="Whether the information should be stored", default=False)


class router(BaseModel):
    initial_route: Literal["direct", "planner"] = Field(description="The chosen route")
