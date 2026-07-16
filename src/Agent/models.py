from pydantic import BaseModel, Field
from typing import List, Literal, Optional


class planner(BaseModel):
    tools_available: List[str] = [
    "read_emails",
    "send_email",
    "reply_to_email",
    "mark_as_read",
    "mark_as_unread",
    "archive_email",
    "trash_email",
    "add_label",
    "remove_label",
    "list_labels",
    "create_draft",
    "get_email_stats",
]
    tool_to_use: List[str] = Field(description="List of tools to execute")
    reason: str = Field(description="Reason for using these tools")
    executing_plan_context: str = Field(description="Execution context for the tools")


class ExtractItem(BaseModel):
    content: str = Field(description="Extracted information or empty string", default="")
    is_new:bool = Field(description="True if this memory is NEW and should be stored. False if duplicate/already known.")


class extract_data(BaseModel):
    memories:ExtractItem = Field(description="Atomic user memories to store") 
    should: bool = Field(description="Whether the information should be stored", default=False)



class router(BaseModel):
    initial_route: Literal["direct", "planner"] = Field(description="The chosen route")

