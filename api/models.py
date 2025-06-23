"""Pydantic models for the API layer."""

from typing import Dict, Any ,Optional
from pydantic import BaseModel, Field
from core.agents.common.agent_factory import AgentTypeEnums

class ChatRequest(BaseModel):
    """Request model for chat endpoint."""
    message: str = Field(..., description="User message to send to the agent")
    chat_id: str = Field(..., description="Unique chat session identifier")
    user_id: str = Field(..., description="Unique user identifier")
    agent_type: AgentTypeEnums = Field(default=AgentTypeEnums.CUSTOMER_SERVICE, description="Type of agent to use")
    extra_metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata for the request")


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""
    content: str = Field(..., description="Agent response content")
    chat_id: str = Field(..., description="Chat session identifier")
    agent_type: str = Field(..., description="Type of agent used")
    timestamp: str = Field(..., description="Response timestamp")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional response metadata")