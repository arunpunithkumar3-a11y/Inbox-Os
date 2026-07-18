from pydantic import BaseModel
from typing import Optional


class AgentRequest(BaseModel):
    query: str
    thread_id: Optional[str] = None
    state: Optional[dict] = None


class AgentEndpointRequest(BaseModel):
    data: AgentRequest
    state: Optional[dict] = None


class ResumeRequest(BaseModel):
    resume_data: dict
    thread_id: str
