from pydantic import BaseModel
from typing import Optional


class AgentRequest(BaseModel):
    query: str
    thread_id: Optional[str] = None

class ResumeRequest(BaseModel):
    resume_data:dict
    thread_id:str