"""Pydantic models for state management services."""

from datetime import datetime
from typing import Dict, Any
from pydantic import BaseModel, Field


class ChatState(BaseModel):
    """Chat state model."""
    chat_id: str
    created_at: str
    updated_at: str
    user_preferences: Dict[str, Any] = Field(default_factory=dict)
    conversation_context: Dict[str, Any] = Field(default_factory=dict)
    
    @classmethod
    def create_default(cls, chat_id: str) -> 'ChatState':
        """Create default chat state."""
        now = datetime.now().isoformat()
        return cls(
            chat_id=chat_id,
            created_at=now,
            updated_at=now
        ) 